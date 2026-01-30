#!/bin/bash

# tockerdui   Uninstaller
# This script removes the application, its virtual environment, and the global shortcut.

set -e

INSTALL_DIR="$HOME/.local/share/tockerdui"
BIN_DIR="$HOME/.local/bin"

echo "🗑️ Uninstalling tockerdui  ..."

# 1. Remove the launcher
if [ -f "$BIN_DIR/tockerdui" ]; then
    echo "Removing launcher from $BIN_DIR..."
    rm "$BIN_DIR/tockerdui"
fi

# 2. Remove the installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing application files from $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
fi

echo ""
echo "✅ Uninstallation complete!"
echo "------------------------------------------------"
echo "tockerdui has been removed from your system."
echo "------------------------------------------------"
