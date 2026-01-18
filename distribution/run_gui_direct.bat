@echo off
:: ============================================================
::  Kling UI - Quick Launch GUI (Python Script Mode)
::  Launches the Tkinter GUI directly without building exe
::  Use this to test before building the executable
:: ============================================================

echo Launching Kling UI (Direct GUI Mode)...
echo.

cd /d "%~dp0"
python gui_launcher.py

if %errorlevel% neq 0 (
    echo.
    echo Error launching GUI. Make sure dependencies are installed:
    echo   pip install requests pillow rich tkinterdnd2
    pause
)
