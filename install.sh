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

# Check for venv module
if ! python3 -m venv --help &> /dev/null;
    then
    echo "❌ Error: python3-venv is missing."
    echo "Please install it: sudo apt install python3-venv (on Debian/Ubuntu)"
    exit 1
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
python3 -m venv "$INSTALL_DIR/venv"

echo "📥 Installing dependencies (this may take a minute)...
"$INSTALL_DIR"/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/tockerdui/requirements.txt" --quiet

echo "🚀 Creating global launcher..."
cat <<EOF > "$BIN_DIR/tockerdui"
#!/bin/bash
export PYTHONPATH="$INSTALL_DIR"
"$INSTALL_DIR/venv/bin/python3" -m tockerdui.main "\$@"
EOF

chmod +x "$BIN_DIR/tockerdui"

echo ""
echo "✨ ✅ Installation Successful! ✨"
echo "------------------------------------------------"
echo "You can now launch the app from anywhere with: tockerdui"


if [[ ":$PATH:" != ":$BIN_DIR:" ]]
    then
    echo "⚠️  Note: $BIN_DIR is not in your PATH."
    echo "Add this line to your ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"$$HOME/.local/bin:$PATH\""
fi
echo "------------------------------------------------"