#!/bin/bash
echo "============================================"
echo "  Net Monitor Widget - Linux Builder"
echo "============================================"
echo ""

echo "[1/3] Creating Virtual Environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "[2/3] Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "[3/3] Building Linux Executable..."
pyinstaller --noconfirm --onefile --windowed --name "NetMonitor" \
    --add-data "style.qss:." \
    main.py

echo ""
echo "[3/3] Done! The Linux executable is available at: dist/NetMonitor"
