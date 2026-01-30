#!/bin/bash

# tockerdui   Installer - Enhanced
set -e

INSTALL_DIR="$HOME/.local/share/tockerdui"
BIN_DIR="$HOME/.local/bin"

echo "🐳 Preparing to install tockerdui  ..."

# Check for python3
if ! command -v python3 &> /dev/null;
    then
    echo "❌ Error: python3 is not installed."
    exit 1
fi

# Check for venv/ensurepip
if ! python3 -m ensurepip --version &> /dev/null; then
    echo "❌ Error: 'ensurepip' is missing."
    echo "Python requires 'python3-venv' to create virtual environments."
    
    if command -v apt &> /dev/null; then
        echo ""
        read -p "Would you like to try installing 'python3-venv' now? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🔑 Sudo password might be required."
            if sudo apt update && sudo apt install -y python3-venv; then
                echo "✅ Package installed."
            else
                echo "❌ Installation failed. Please install manually."
                exit 1
            fi
        else
            echo "Installation aborted by user."
            exit 1
        fi
    else
        echo "Please install 'python3-venv' for your distribution manually."
        exit 1
    fi
fi

echo "📦 Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

echo "📂 Copying source files..."
mkdir -p "$INSTALL_DIR/tockerdui"
cp -r src/tockerdui/. "$INSTALL_DIR/tockerdui/"
cp requirements.txt "$INSTALL_DIR/tockerdui/"
# Remove nested .git or build artifacts from install dir if any
rm -rf "$INSTALL_DIR/tockerdui/.git" "$INSTALL_DIR/tockerdui/venv"

echo "🔧 Creating isolated virtual environment..."
if ! python3 -m venv "$INSTALL_DIR/venv"; then
    echo "❌ Error: Failed to create virtual environment."
    echo "Try installing venv: sudo apt install python3-venv"
    exit 1
fi

echo "📥 Installing dependencies (this may take a minute)...
"$INSTALL_DIR"/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/tockerdui/requirements.txt" --quiet

# Save source path for updates
echo "$PWD" > "$INSTALL_DIR/source_path"
cp uninstall.sh "$INSTALL_DIR/"

echo "🚀 Creating global launcher..."
cat <<EOF > "$BIN_DIR/tockerdui"
#!/bin/bash

# Handle CLI commands
if [ "\$1" == "update" ]; then
    SOURCE_PATH=\$(cat "$INSTALL_DIR/source_path")
    if [ -d "\$SOURCE_PATH" ]; then
        echo "🔄 Switching to source directory: \$SOURCE_PATH"
        cd "\$SOURCE_PATH" && ./update.sh
    else
        echo "❌ Source directory not found: \$SOURCE_PATH"
        echo "Unable to update automatically via git."
        exit 1
    fi
    exit 0
elif [ "\$1" == "uninstall" ]; then
    bash "$INSTALL_DIR/uninstall.sh"
    exit 0
fi

# Run Application
export PYTHONPATH="$INSTALL_DIR"
"$INSTALL_DIR/venv/bin/python3" -m tockerdui.main "\$@"
EOF

chmod +x "$BIN_DIR/tockerdui"

echo ""
echo "✨ ✅ Installation Successful! ✨"
echo "------------------------------------------------"
echo "You can now launch the app from anywhere with: tockerdui"
echo "Available commands:"
echo "  tockerdui           - Run the application"
echo "  tockerdui update    - Pull changes and update"
echo "  tockerdui uninstall - Remove the application"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "⚠️  Note: $BIN_DIR is not in your PATH."
    echo "Add this line to your ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo "------------------------------------------------"