#!/bin/bash
echo "============================================"
echo "  Net Monitor Widget - Mac Builder"
echo "============================================"
echo ""

echo "[1/4] Creating Virtual Environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "[2/4] Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "[3/4] Building macOS App..."
# On macOS, --windowed creates a .app bundle, which is the standard way to distribute single-click macOS apps without opening a terminal
pyinstaller --noconfirm --onedir --windowed --name "NetMonitor" \
    --add-data "style.qss:." \
    main.py

echo ""
echo "[4/4] Done! The Mac app is available at: dist/NetMonitor.app"
echo "You can move NetMonitor.app to your Applications folder."
