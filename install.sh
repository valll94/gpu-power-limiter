#!/bin/bash
#
# GPU Power Limiter Installation Script
#
set -e

echo "Installing GPU Power Limiter..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Installation directory
INSTALL_DIR="/opt/gpu-power-limiter"

# Ensure Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed"
    exit 1
fi

# Install required Python packages
echo "Installing required Python packages..."

# Try to install pynvml using pipx (for Arch Linux)
if command -v pipx &> /dev/null; then
    echo "Detected pipx - using it to install pynvml in an isolated environment"
    
    # Create a small Python script to check if pynvml can be imported
    cat > /tmp/check_pynvml.py << EOF
try:
    import pynvml
    print("pynvml is already installed")
    exit(0)
except ImportError:
    print("pynvml is not installed")
    exit(1)
EOF
    
    # Check if pynvml can be imported
    if python3 /tmp/check_pynvml.py &> /dev/null; then
        echo "pynvml is already installed"
    else
        echo "Installing pynvml using pipx..."
        pipx install pynvml || {
            echo "Trying pip install --user pynvml..."
            pip install --user pynvml || {
                echo "Error: Could not install pynvml."
                echo "Please install it manually using: pip install --user pynvml"
                exit 1
            }
        }
    fi
# For other distributions with pip
else
    echo "Trying to install pynvml using pip..."
    cat > /tmp/check_pynvml.py << EOF
try:
    import pynvml
    print("pynvml is already installed")
    exit(0)
except ImportError:
    print("pynvml is not installed")
    exit(1)
EOF
    
    if python3 /tmp/check_pynvml.py &> /dev/null; then
        echo "pynvml is already installed"
    else
        pip install --user pynvml || sudo pip install pynvml || {
            echo "Error: Could not install pynvml."
            echo "Please install it manually using: pip install --user pynvml"
            exit 1
        }
    fi
fi

# Clean up temporary files
rm -f /tmp/check_pynvml.py

# Create installation directory
echo "Creating installation directory at ${INSTALL_DIR}..."
sudo mkdir -p "$INSTALL_DIR"

# Copy files to installation directory
echo "Copying files to installation directory..."
sudo cp gpus-powerlimit.py "$INSTALL_DIR/"
sudo cp docker-protect.sh "$INSTALL_DIR/"

# Make scripts executable
sudo chmod +x "$INSTALL_DIR/gpus-powerlimit.py"
sudo chmod +x "$INSTALL_DIR/docker-protect.sh"

# Update docker-protect.sh to use system docker
echo "Updating docker-protect.sh..."
sudo sed -i 's/PYTHON_SCRIPT="${SCRIPT_DIR}\/gpus-powerlimit.py"/PYTHON_SCRIPT="\/opt\/gpu-power-limiter\/gpus-powerlimit.py"/' "$INSTALL_DIR/docker-protect.sh"
sudo sed -i 's/exec docker "$@"/exec \/usr\/bin\/docker "$@"/' "$INSTALL_DIR/docker-protect.sh"

# Create docker alias
echo "Setting up Docker protection..."

# Create alias in /etc/profile.d
if [ -d "/etc/profile.d" ]; then
    echo "Creating system-wide docker alias..."
    cat > /tmp/docker-alias.sh << EOF
#!/bin/bash
# Alias docker command to use GPU power limit protection
alias docker='/opt/gpu-power-limiter/docker-protect.sh'
EOF
    sudo mv /tmp/docker-alias.sh /etc/profile.d/docker-alias.sh
    sudo chmod +x /etc/profile.d/docker-alias.sh
    echo "System-wide alias created in /etc/profile.d/docker-alias.sh"
    echo "It will be active for all users after they log in again"
    echo "You can manually activate it now with: source /etc/profile.d/docker-alias.sh"
fi

# Install systemd services
if command -v systemctl &> /dev/null; then
    echo "Installing systemd services..."
    
    # Copy service files
    sudo cp "$SCRIPT_DIR/gpu-power-limiter.service" /etc/systemd/system/
    sudo cp "$SCRIPT_DIR/gpu-checker.path" /etc/systemd/system/
    sudo cp "$SCRIPT_DIR/gpu-config-update.service" /etc/systemd/system/
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable and start services
    sudo systemctl enable gpu-power-limiter.service
    sudo systemctl start gpu-power-limiter.service || echo "Warning: Failed to start gpu-power-limiter.service"
    
    sudo systemctl enable gpu-checker.path
    sudo systemctl start gpu-checker.path || echo "Warning: Failed to start gpu-checker.path"
    
    echo "Systemd services installed and started"
else
    echo "Systemd not found, skipping service installation"
    echo "You will need to set up a startup method manually"
fi

# Create a symlink for convenience
sudo ln -sf "$INSTALL_DIR/gpus-powerlimit.py" /usr/local/bin/gpu-power-limiter

# Run initial power limit check
echo "Running initial power limit check..."
sudo python3 "$INSTALL_DIR/gpus-powerlimit.py" --check || echo "Warning: Power limit check failed. Please check your GPU configuration."

echo "Installation complete!"
echo ""
echo "Usage:"
echo "  - Docker commands are now protected via system alias (may require relogin)"
echo "  - Edit /opt/gpu-power-limiter/gpu_config.json to change GPU power limits"
echo "  - Run 'gpu-power-limiter --help' for more options"
echo ""
echo "Commands:"
echo "  - Check power limits: gpu-power-limiter --check"
echo "  - Apply power limits: gpu-power-limiter"
echo "  - Restore Docker: gpu-power-limiter --restore-docker"
echo ""
echo "Service management:"
echo "  - Check service status: systemctl status gpu-power-limiter.service"
echo "  - View logs: journalctl -u gpu-power-limiter.service" 