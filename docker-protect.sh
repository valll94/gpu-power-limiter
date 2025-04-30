#!/bin/bash
#
# Docker Protection Wrapper
# Makes sure GPU power limits are correctly set before running Docker commands
#

SCRIPT_DIR="$(dirname "$0")"
PYTHON_SCRIPT="${SCRIPT_DIR}/gpus-powerlimit.py"
CACHE_FILE="/tmp/gpu-power-check.cache"
CACHE_TTL=30  # Cache validity in seconds

# Check if the script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: GPU Power Limiter script not found at $PYTHON_SCRIPT"
    echo "System has been blocked for safety. Please contact system admin."
    exit 1
fi

# Check if cache is valid (to reduce overhead)
if [ -f "$CACHE_FILE" ] && [ $(($(date +%s) - $(stat -c %Y "$CACHE_FILE"))) -lt "$CACHE_TTL" ]; then
    # Cache is valid, bypass the check for better performance
    exec /usr/bin/docker "$@"
    exit $?
fi

# Run the power limit check (silent mode)
if python3 "$PYTHON_SCRIPT" --check &>/dev/null; then
    # Success - update cache and run command
    touch "$CACHE_FILE"
    exec /usr/bin/docker "$@"
else
    # Only show output on failure
    echo "ERROR: GPU power limits are not set correctly!"
    echo "Docker operations blocked for safety. Please correct power limits first."
    echo "To restore Docker after fixing power limits: python3 $PYTHON_SCRIPT --restore-docker"
    exit 1
fi 