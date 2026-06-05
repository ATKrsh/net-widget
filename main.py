"""
main.py
Entry point for Net Widget.
"""

import sys
import os
import warnings
from pathlib import Path

# Suppress wmi package import syntax warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="wmi")

# Redirect stdout/stderr to a log file in bundled mode to prevent crashes
if getattr(sys, "frozen", False):
    try:
        log_dir = Path.home() / ".net-widget"
        log_dir.mkdir(parents=True, exist_ok=True)
        # open with line buffering so logs are written immediately
        log_file = open(log_dir / "app.log", "w", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        # Fallback if log file cannot be created
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

# Ensure the script's directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication
from widget import NetWidget


def main():
    # Enable high-DPI support
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Net Monitor")
    app.setOrganizationName("net-widget")

    # Set a modern font
    from PyQt5.QtGui import QFont

    font = QFont("Segoe UI", 9)
    font.setHintingPreference(QFont.PreferDefaultHinting)
    app.setFont(font)

    # Don't quit when last window closes (tray icon keeps it alive)
    app.setQuitOnLastWindowClosed(False)

    window = NetWidget()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
