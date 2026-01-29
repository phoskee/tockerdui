#!/bin/bash

# Dockterm V2 Uninstaller
# This script removes the application, its virtual environment, and the global shortcut.

set -e

INSTALL_DIR="$HOME/.local/share/dockterm"
BIN_DIR="$HOME/.local/bin"

echo "🗑️ Uninstalling Dockterm V2..."

# 1. Remove the launcher
if [ -f "$BIN_DIR/dockterm" ]; then
    echo "Removing launcher from $BIN_DIR..."
    rm "$BIN_DIR/dockterm"
fi

# 2. Remove the installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing application files from $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
fi

echo ""
echo "✅ Uninstallation complete!"
echo "------------------------------------------------"
echo "Dockterm has been removed from your system."
echo "------------------------------------------------"
