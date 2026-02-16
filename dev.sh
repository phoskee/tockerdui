#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN not found"
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv in $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "Installing runtime dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ "${INSTALL_DEV_DEPS:-1}" = "1" ]; then
  echo "Installing dev dependencies..."
  python -m pip install -e ".[dev]"
fi

export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"
export TOCKERDUI_DEBUG="${TOCKERDUI_DEBUG:-1}"
export PYTHONUNBUFFERED=1

echo "Starting tockerdui (debug mode)..."
exec python -m tockerdui.main "$@"
