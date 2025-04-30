# GPU Power Management System

## Introduction

### Purpose
This system enforces power limits on NVIDIA GPUs to prevent excessive power consumption, ensuring system stability and safety. It also manages Docker to prevent operations when GPU power limits are not correctly configured.

### Scope
Covers power management for all NVIDIA GPUs in the system via a persistent daemon and Docker safety mechanisms.

### Audience
System administrators managing GPU resources and Docker containers.

## Overview

### Architecture
The system consists of the following components:

1. **GPU Power Limiter Script** (gpus-powerlimit.py): 
   - Python daemon that sets and monitors power limits
   - Manages Docker service when limits are incorrect
   - Provides CLI options for various operations

2. **Systemd Integration**:
   - Service to run the script as a persistent daemon
   - Path unit to monitor configuration changes
   - Service to automatically apply config changes

3. **Docker Protection**:
   - Automatically stops and disables Docker when limits are incorrect
   - Wrapper script for safe Docker operations

### Technologies Used
- Python 3
- NVIDIA Management Library (pynvml)
- systemd
- Bash
- JSON (for configuration)

### Dependencies
- Python 3
- pynvml package
- systemd (Linux only)

## Guide

### Prerequisites
1. NVIDIA drivers installed
2. Python 3 installed
3. pynvml package installed: `pip install pynvml`

### Installation

The easiest way to install is using the provided installation script:

```bash
# Make the script executable
chmod +x install.sh

# Run the installation script as root
sudo ./install.sh
```

This will:
- Install required Python packages
- Make scripts executable
- Install systemd services
- Create a Docker safety wrapper command

If you prefer to install manually:

1. Install the pynvml package:
   ```bash
   pip install pynvml
   ```

2. Make the scripts executable:
   ```bash
   chmod +x gpus-powerlimit.py
   chmod +x docker-protect.sh
   ```

3. Configure GPU power limits:
   ```bash
   # The script will create a default config file on first run
   # Edit the file to set custom power limits for each GPU
   vi gpu_config.json
   ```

4. Install the systemd services:
   ```bash
   # Copy service files
   sudo cp gpu-power-limiter.service /etc/systemd/system/
   sudo cp gpu-checker.path /etc/systemd/system/
   sudo cp gpu-config-update.service /etc/systemd/system/
   
   # Reload and enable
   sudo systemctl daemon-reload
   sudo systemctl enable gpu-power-limiter.service
   sudo systemctl start gpu-power-limiter.service
   sudo systemctl enable gpu-checker.path
   sudo systemctl start gpu-checker.path
   ```

5. Set up the Docker protection wrapper:
   ```bash
   sudo ln -sf $(pwd)/docker-protect.sh /usr/local/bin/docker-safe
   ```

### Configuration

The script uses a JSON configuration file (`gpu_config.json`) with the following structure:

```json
{
    "gpu_power_limits": {
        "0": 300,  // GPU 0: 300W
        "1": 250   // GPU 1: 250W
    },
    "check_interval": 60,
    "manage_docker": true
}
```

- **gpu_power_limits**: A dictionary mapping GPU indices to their power limits in watts
- **check_interval**: How often (in seconds) the daemon should check and apply power limits
- **manage_docker**: Whether to manage Docker service when limits are incorrect (true/false)

The configuration file is created automatically with default settings if it doesn't exist. You can edit it to set different power limits for each GPU.

### Docker Protection

There are two ways to protect Docker operations:

1. **Automatic Protection (via the daemon)**: 
   - The daemon monitors GPU power limits
   - If limits are incorrect, it automatically stops, disables, and masks Docker
   - You can restore Docker after fixing limits using `python3 gpus-powerlimit.py --restore-docker`

2. **Command Wrapper**:
   - Use `docker-safe` instead of `docker` for protected operations
   - This checks power limits before running any Docker command
   - Automatically blocks operations if limits are incorrect

### Core Functionality
- Sets custom power limits on individual NVIDIA GPUs
- Regularly checks and re-applies limits (default: every 60 seconds)
- Provides detailed logging to both console and file
- Dynamically reloads configuration to apply changes without restart
- Stops and disables Docker when GPU power limits are incorrect

### Command Line Options

The Python script supports several command-line options:

```
--daemon        Run as a daemon
--verbose       Enable verbose logging
--check         Check if power limits are correctly set
--no-docker     Do not manage Docker service
--stop-docker   Stop Docker service and exit
--restore-docker Restore Docker service if it was disabled
```

### Deployment Process
1. Install using the provided script
2. Configure specific power limits for each GPU
3. Use `docker-safe` for Docker operations

## Support and Maintenance

### Troubleshooting
- Check service status: `systemctl status gpu-power-limiter.service`
- Check logs: `journalctl -u gpu-power-limiter.service` and `/var/log/gpu-power-limiter.log`
- Test script manually: `python3 gpus-powerlimit.py --check`
- Verify configuration: `cat gpu_config.json`

### Frequently Asked Questions
- **Q: Why set different power limits for different GPUs?**  
  A: Different GPU models may have different thermal and power characteristics. Setting appropriate limits for each GPU optimizes performance while ensuring system stability.
  
- **Q: How do I change the power limits?**  
  A: Edit the `gpu_config.json` file. Changes will be applied automatically by the path watcher service.
  
- **Q: What happens if Docker was disabled due to incorrect power limits?**  
  A: Fix the power limits, then run `python3 gpus-powerlimit.py --restore-docker` to restore Docker.
  
- **Q: Can I still use Docker without the safety check?**  
  A: Yes, you can still use the regular `docker` command, but it's recommended to use `docker-safe` for safety.

- **Q: How can I disable Docker management?**  
  A: Set `"manage_docker": false` in the config file, or run the script with `--no-docker`.

## Change Log

### Version History
- 1.0.0: Initial implementation with basic power limiting
- 1.1.0: Added daemon mode, systemd service, and blocking mechanism
- 1.2.0: Added per-GPU power limit configuration and dynamic config reloading
- 1.3.0: Added Docker service management, configuration file monitoring, and wrapper script

### Change Summary
- Added proper error handling
- Implemented daemon mode for continuous operation
- Created systemd service for persistent execution
- Added Docker protection mechanisms
- Added JSON configuration for per-GPU power limits
- Added automatic config monitoring via systemd path unit 