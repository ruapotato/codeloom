#!/bin/bash
# codeloom installer
# Installs codeloom to make it available system-wide

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "codeloom installer"
echo "=================="
echo

# Check for Claude Code
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: Claude Code CLI not found.${NC}"
    echo "Please install Claude Code first: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found.${NC}"
    echo "Please install Python 3 first."
    exit 1
fi

# Determine install location
if [ "$1" = "--system" ]; then
    INSTALL_DIR="/usr/local/bin"
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}System install requires root. Using sudo...${NC}"
        SUDO="sudo"
    fi
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: ./install.sh [OPTIONS]"
    echo
    echo "Options:"
    echo "  --system    Install to /usr/local/bin (requires sudo)"
    echo "  --uninstall Remove codeloom from PATH"
    echo "  -h, --help  Show this help message"
    echo
    echo "Default: Install to ~/.local/bin"
    exit 0
elif [ "$1" = "--uninstall" ]; then
    echo "Uninstalling codeloom..."
    if [ -L "${HOME}/.local/bin/codeloom" ]; then
        rm "${HOME}/.local/bin/codeloom"
        echo -e "${GREEN}Removed from ~/.local/bin${NC}"
    fi
    if [ -L "/usr/local/bin/codeloom" ]; then
        sudo rm "/usr/local/bin/codeloom"
        echo -e "${GREEN}Removed from /usr/local/bin${NC}"
    fi
    echo "Done."
    exit 0
fi

# Create install directory if needed
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Creating $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
fi

# Make launcher executable
chmod +x "$SCRIPT_DIR/codeloom"

# Create symlink
echo "Installing to $INSTALL_DIR..."
$SUDO ln -sf "$SCRIPT_DIR/codeloom" "$INSTALL_DIR/codeloom"

# Check if install dir is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo
    echo -e "${YELLOW}Note: $INSTALL_DIR is not in your PATH.${NC}"
    echo "Add this to your ~/.bashrc or ~/.zshrc:"
    echo
    echo "  export PATH=\"\$PATH:$INSTALL_DIR\""
    echo
fi

echo
echo -e "${GREEN}Installation complete!${NC}"
echo
echo "Run 'codeloom' to start."
echo "Run 'codeloom --help' for options."
