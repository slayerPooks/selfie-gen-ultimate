@echo off
cd /d "%~dp0"
title Kling UI

:: ServBay Python has all required packages (tkinterdnd2, etc.)
:: Using .exe directly — avoids ServBay's python.cmd wrapper breaking bat return flow
set PYTHON=C:\ServBay\packages\python\current\python.exe

if not exist "%PYTHON%" (
    echo ServBay Python not found at %PYTHON%
    echo Trying system python...
    set PYTHON=python
)

echo Starting Kling UI...
echo.

"%PYTHON%" -u gui_launcher.py
set ERR=%errorlevel%

if %ERR% neq 0 (
    echo.
    echo ============================================
    echo   CRASHED  (exit code: %ERR%)
    echo ============================================
    echo.
    if exist crash_log.txt (
        echo --- crash_log.txt ---
        type crash_log.txt
        echo.
    )
)

pause
