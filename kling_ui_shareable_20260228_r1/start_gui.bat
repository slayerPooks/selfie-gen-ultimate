@echo off
cd /d "%~dp0"
title Kling UI

:: Resolution order:
:: 1) KLING_UI_PYTHON env var (explicit override)
:: 2) Local venv python
:: 3) System python from PATH
if defined KLING_UI_PYTHON (
    set PYTHON=%KLING_UI_PYTHON%
) else (
    if exist "%~dp0venv\Scripts\python.exe" (
        set PYTHON=%~dp0venv\Scripts\python.exe
    ) else (
        set PYTHON=python
    )
)

if not exist "%PYTHON%" (
    echo Python not found at %PYTHON%
    echo Falling back to system python from PATH...
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
