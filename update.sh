#!/bin/bash
set -e

echo "🐳 Updating Tockerdui..."

# Git pull to get latest changes
echo "⬇️  Pulling latest version..."
git pull

# Run install script to update installation
echo "🔄 Re-installing..."
./install.sh

echo ""
echo "✨ Update Complete! ✨"
