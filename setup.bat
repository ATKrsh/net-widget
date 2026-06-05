@echo off
title Net Widget - Setup
echo ============================================
echo   Net Monitor Widget - Setup and Launch
echo ============================================
echo.

echo [1/2] Installing dependencies...
py -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/2] Launching Net Widget...
py main.py

pause
