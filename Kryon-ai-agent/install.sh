#!/usr/bin/env bash
# Kryon install script — Linux / macOS / WSL
# Full implementation lands in File #15. This is a placeholder that verifies Python.

set -euo pipefail

echo "🐙 Kryon install (placeholder — full installer lands in File #15)"

# Verify Python 3.12+
if ! command -v python3.12 >/dev/null 2>&1; then
    if ! python3 --version 2>/dev/null | grep -q "3.12"; then
        echo "❌ Python 3.12+ is required"
        echo "   Install with: sudo apt install python3.12 (Debian/Ubuntu)"
        echo "                 or: brew install python@3.12 (macOS)"
        exit 1
    fi
fi

# Create venv
python3.12 -m venv .venv
source .venv/bin/activate

# Install
pip install --upgrade pip
pip install -e ".[dev]"

echo "✅ Kryon installed. Try: kryon --version"
