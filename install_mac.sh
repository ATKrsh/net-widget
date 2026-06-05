#!/bin/bash
echo "============================================"
echo "  Net Monitor Widget - Mac Setup"
echo "============================================"
echo ""

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
