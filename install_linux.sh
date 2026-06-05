#!/bin/bash
echo "============================================"
echo "  Net Monitor Widget - Linux Setup"
echo "============================================"
echo ""

# Install python3-venv on apt-based systems if missing
if command -v apt-get &> /dev/null; then
    dpkg -s python3-venv &> /dev/null
    if [ $? -ne 0 ]; then
        echo "Installing python3-venv (requires sudo)..."
        sudo apt-get update && sudo apt-get install -y python3-venv
    fi
fi

echo "[1/3] Creating Virtual Environment..."
python3 -m venv .venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment. Make sure Python 3 is installed."
    exit 1
fi

echo ""
echo "[2/3] Installing dependencies..."
source .venv/bin/activate
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: pip install failed."
    exit 1
fi

echo ""
echo "[3/3] Launching Net Widget..."
python main.py
