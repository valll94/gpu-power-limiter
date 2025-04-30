#!/usr/bin/env python3
"""
GPU Power Limiter

This script sets power limits on NVIDIA GPUs to prevent excessive power consumption.
It dynamically detects available GPUs and applies specified power limits to each.
It can also stop and disable Docker if power limits are not configured properly.
"""

import sys
import logging
import json
import os
import time
import argparse
import signal
import subprocess
from pynvml import nvmlInit, nvmlDeviceGetCount, nvmlDeviceGetHandleByIndex, nvmlDeviceSetPowerManagementLimit
from pynvml import nvmlDeviceGetName, nvmlDeviceGetPowerManagementLimit, NVMLError

# Configuration
# Use a fixed path for configuration, regardless of how the script is called
CONFIG_PATH = "/opt/gpu-power-limiter/gpu_config.json"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/gpu-power-limiter.log', 'a')
    ]
)
logger = logging.getLogger('gpu-power-limiter')

# Global flag for graceful shutdown
running = True

def signal_handler(sig, frame):
    """Handle signals to allow graceful shutdown"""
    global running
    logger.info("Received shutdown signal, exiting gracefully...")
    running = False

def run_command(command):
    """Run a shell command and return the output and return code"""
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        logger.error(f"Error running command '{command}': {e}")
        return "", str(e), -1

def is_docker_running():
    """Check if Docker service is running"""
    _, _, rc = run_command("systemctl is-active --quiet docker")
    return rc == 0

def is_docker_enabled():
    """Check if Docker service is enabled"""
    _, _, rc = run_command("systemctl is-enabled --quiet docker")
    return rc == 0

def is_docker_masked():
    """Check if Docker service is masked"""
    _, _, rc = run_command("systemctl is-masked --quiet docker")
    return rc == 0

def stop_docker():
    """Stop Docker service"""
    logger.info("Stopping Docker service...")
    stdout, stderr, rc = run_command("systemctl stop docker")
    if rc != 0:
        logger.error(f"Failed to stop Docker service: {stderr}")
        return False
    logger.info("Docker service stopped successfully")
    return True

def disable_docker():
    """Disable Docker service from starting at boot"""
    logger.info("Disabling Docker service...")
    stdout, stderr, rc = run_command("systemctl disable docker")
    if rc != 0:
        logger.error(f"Failed to disable Docker service: {stderr}")
        return False
    logger.info("Docker service disabled successfully")
    return True

def mask_docker():
    """Mask Docker service for additional safety"""
    logger.info("Masking Docker service...")
    stdout, stderr, rc = run_command("systemctl mask docker")
    if rc != 0:
        logger.error(f"Failed to mask Docker service: {stderr}")
        return False
    logger.info("Docker service masked successfully")
    return True

def unmask_docker():
    """Unmask Docker service"""
    logger.info("Unmasking Docker service...")
    stdout, stderr, rc = run_command("systemctl unmask docker")
    if rc != 0:
        logger.error(f"Failed to unmask Docker service: {stderr}")
        return False
    logger.info("Docker service unmasked successfully")
    return True

def enable_docker():
    """Enable Docker service"""
    logger.info("Enabling Docker service...")
    stdout, stderr, rc = run_command("systemctl enable docker")
    if rc != 0:
        logger.error(f"Failed to enable Docker service: {stderr}")
        return False
    logger.info("Docker service enabled successfully")
    return True

def start_docker():
    """Start Docker service"""
    logger.info("Starting Docker service...")
    stdout, stderr, rc = run_command("systemctl start docker")
    if rc != 0:
        logger.error(f"Failed to start Docker service: {stderr}")
        return False
    logger.info("Docker service started successfully")
    return True

def manage_docker_safety(limits_ok, config):
    """Manage Docker service based on GPU power limits status"""
    if not config.get("manage_docker", True):
        logger.debug("Docker management is disabled in config")
        return
    
    if not limits_ok:
        logger.warning("GPU power limits are incorrect, checking Docker...")
        if is_docker_running():
            logger.critical("CRITICAL: Docker is running with incorrect GPU power limits")
            stop_docker()
            disable_docker()
            mask_docker()
            logger.warning("Docker has been stopped and disabled for safety reasons")
            logger.info("Please configure GPU power limits correctly and then run the script with --restore-docker")
    else:
        logger.debug("GPU power limits are correct, Docker can run")

def restore_docker():
    """Restore Docker service if it was previously masked/disabled"""
    logger.info("Checking Docker service status...")
    
    # Always unmask first, regardless of current status
    if is_docker_masked():
        logger.info("Docker is masked, unmasking first...")
        if not unmask_docker():
            logger.error("Failed to unmask Docker service")
            return False
    
    # Then enable if needed
    if not is_docker_enabled():
        logger.info("Docker is disabled, enabling...")
        if not enable_docker():
            logger.error("Failed to enable Docker service")
            return False
    
    # Finally, start if not running
    if not is_docker_running():
        logger.info("Docker is not running, starting...")
        if not start_docker():
            logger.error("Failed to start Docker service")
            return False
    
    logger.info("Docker has been successfully restored")
    return True

def load_config():
    """Load configuration from file or create with defaults if not exists."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {CONFIG_PATH}")
                return config
        else:
            # Create default config file
            with open(CONFIG_PATH, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
                logger.info(f"Created default configuration at {CONFIG_PATH}")
            return DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return DEFAULT_CONFIG

def get_device_name(device):
    """Get the device name and handle different pynvml versions gracefully"""
    try:
        name = nvmlDeviceGetName(device)
        # Check if result is already a string (newer pynvml versions)
        if isinstance(name, str):
            return name
        # Otherwise it's bytes (older pynvml versions)
        return name.decode('utf-8')
    except Exception as e:
        logger.warning(f"Error getting device name: {e}")
        return "Unknown GPU"

def verify_gpu_power_limits(config):
    """Verify that current GPU power limits match the configured values."""
    try:
        nvmlInit()
        gpu_count = nvmlDeviceGetCount()
        
        if gpu_count == 0:
            logger.warning("No NVIDIA GPUs detected")
            return False
        
        logger.debug(f"Found {gpu_count} NVIDIA GPUs")
        
        for i in range(gpu_count):
            try:
                device = nvmlDeviceGetHandleByIndex(i)
                device_name = get_device_name(device)
                
                # Get power limit for this GPU (use default if not specified)
                expected_limit = config["gpu_power_limits"].get(str(i), 300)
                expected_limit_mw = expected_limit * 1000  # Convert to milliwatts
                
                # Get current power limit
                current_limit_mw = nvmlDeviceGetPowerManagementLimit(device)
                current_limit = current_limit_mw / 1000  # Convert to watts
                
                if abs(current_limit_mw - expected_limit_mw) > 1000:  # Allow 1W tolerance
                    logger.warning(f"GPU {i} ({device_name}) power limit is {current_limit}W, expected {expected_limit}W")
                    return False
                else:
                    logger.debug(f"GPU {i} ({device_name}) power limit verified: {current_limit}W")
            except NVMLError as e:
                logger.error(f"Failed to verify power limit on GPU {i}: {e}")
                return False
        
        return True
    except NVMLError as e:
        logger.error(f"NVML initialization failed: {e}")
        return False

def set_gpu_power_limits(config):
    """Set power limits for all available NVIDIA GPUs based on configuration."""
    try:
        nvmlInit()
        gpu_count = nvmlDeviceGetCount()
        
        if gpu_count == 0:
            logger.warning("No NVIDIA GPUs detected")
            return False
        
        logger.info(f"Found {gpu_count} NVIDIA GPUs")
        success = True
        
        for i in range(gpu_count):
            try:
                device = nvmlDeviceGetHandleByIndex(i)
                device_name = get_device_name(device)
                
                # Get power limit for this GPU (use default if not specified)
                power_limit = config["gpu_power_limits"].get(str(i), 300)
                power_limit_mw = power_limit * 1000  # Convert to milliwatts
                
                # Get current power limit
                current_limit_mw = nvmlDeviceGetPowerManagementLimit(device)
                current_limit = current_limit_mw / 1000  # Convert to watts
                
                # Only update if different (with 1W tolerance)
                if abs(current_limit_mw - power_limit_mw) > 1000:  # Allow 1W tolerance
                    nvmlDeviceSetPowerManagementLimit(device, power_limit_mw)
                    logger.info(f"Set power limit of {power_limit}W on GPU {i} ({device_name})")
                else:
                    logger.info(f"GPU {i} ({device_name}) already at desired power limit: {current_limit}W")
            except NVMLError as e:
                logger.error(f"Failed to set power limit on GPU {i}: {e}")
                success = False
        
        return success
    except NVMLError as e:
        logger.error(f"NVML initialization failed: {e}")
        return False

def run_daemon(config):
    """Run as a daemon, setting power limits only when needed."""
    global running
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting GPU power limiter daemon")
    check_interval = config.get("check_interval", 60)
    
    # Initial power limit setting
    success = set_gpu_power_limits(config)
    if not success:
        logger.error("Failed to set initial GPU power limits")
        # Check Docker on startup if managing is enabled
        if config.get("manage_docker", True):
            manage_docker_safety(False, config)
    
    # Main daemon loop
    while running:
        try:
            # Reload config to check for changes
            current_config = load_config()
            
            # Check if power limits are correct
            limits_ok = verify_gpu_power_limits(current_config)
            
            # Only apply limits if they're not already correct
            if not limits_ok:
                logger.info("Power limits need adjustment, applying...")
                success = set_gpu_power_limits(current_config)
                # Check Docker after applying limits
                if current_config.get("manage_docker", True):
                    manage_docker_safety(success, current_config)
            else:
                logger.debug("Power limits are correctly set, no action needed")
                
            # Sleep but with interruption checking
            for _ in range(check_interval):
                if not running:
                    break
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")
            time.sleep(5)  # Short sleep on error

def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description="GPU Power Limiter")
    parser.add_argument("--daemon", action="store_true", help="Run as a daemon")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--check", action="store_true", help="Check if power limits are correctly set")
    parser.add_argument("--no-docker", action="store_true", help="Do not manage Docker service")
    parser.add_argument("--stop-docker", action="store_true", help="Stop Docker service and exit")
    parser.add_argument("--restore-docker", action="store_true", help="Restore Docker service if it was disabled")
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Load configuration
    config = load_config()
    
    # Override Docker management from config if --no-docker is specified
    if args.no_docker:
        config["manage_docker"] = False
    
    # Execute based on arguments
    if args.stop_docker:
        if is_docker_running():
            stop_docker()
            disable_docker()
            mask_docker()
            return 0
        else:
            logger.info("Docker is not running")
            return 0
    elif args.restore_docker:
        return 0 if restore_docker() else 1
    elif args.check:
        limits_ok = verify_gpu_power_limits(config)
        if limits_ok:
            logger.info("All GPU power limits are correctly set")
            return 0
        else:
            logger.error("GPU power limits are not correctly set")
            if config.get("manage_docker", True):
                manage_docker_safety(False, config)
            return 1
    elif args.daemon:
        run_daemon(config)
        return 0
    else:
        success = set_gpu_power_limits(config)
        if config.get("manage_docker", True) and not success:
            manage_docker_safety(False, config)
        return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())