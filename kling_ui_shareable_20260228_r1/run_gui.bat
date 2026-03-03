@echo off
setlocal
:: ============================================================
::  Kling UI - GUI Launcher
::  Launches gui_launcher.py with venv python if available,
::  falls back to system python.
:: ============================================================

set BATCH_DIR=%~dp0
set GUI_SCRIPT=%BATCH_DIR%gui_launcher.py
set VENV_PYTHON=%BATCH_DIR%venv\Scripts\python.exe

:: Prefer venv python, fall back to system python
if exist "%VENV_PYTHON%" (
    set PYTHON=%VENV_PYTHON%
    echo Using venv python: %VENV_PYTHON%
) else (
    set PYTHON=python
    echo venv not found, using system python.
    echo Run run_kling_ui.bat first if you need dependencies installed.
)

echo Starting Kling UI GUI...
echo.

"%PYTHON%" -u "%GUI_SCRIPT%"
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% neq 0 (
    echo ============================================
    echo   CRASH  ^(exit code: %EXIT_CODE%^)
    echo ============================================
    echo.
    echo Check crash_log.txt in this folder for details.
    echo.
)

echo Press any key to close...
pause >nul
endlocal
