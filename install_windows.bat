@echo off
title Net Widget - Windows Setup
echo ============================================
echo   Net Monitor Widget - Windows Setup
echo ============================================
echo.

echo [1/3] Creating Virtual Environment...
python -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create virtual environment. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Launching Net Widget...
python main.py

pause
