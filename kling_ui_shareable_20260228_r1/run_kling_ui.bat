@echo off
setlocal

:: ============================================================
::  Kling UI Launcher - Auto-venv setup with dependency check
:: ============================================================

set BATCH_DIR=%~dp0

:: Clean up problematic "nul" file if it exists
if exist "%BATCH_DIR%nul" del /f /q "%BATCH_DIR%nul" 2>nul

set SCRIPT_PATH=%BATCH_DIR%kling_automation_ui.py
set VENV_DIR=%BATCH_DIR%venv
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe
set VENV_PIP=%VENV_DIR%\Scripts\pip.exe
set REQUIREMENTS=%BATCH_DIR%requirements.txt

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   ERROR: Python is not installed
    echo ============================================
    echo.
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

python -c "import tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   WARNING: tkinter not found
    echo ============================================
    echo.
    echo tkinter is required for GUI mode.
    echo Please reinstall Python with the "tcl/tk" option enabled.
    echo.
    echo The app will continue but GUI mode may not work.
    echo.
    timeout /t 5
)

if not exist "%VENV_PYTHON%" (
    echo.
    echo ============================================
    echo   First-time setup: Creating virtual environment...
    echo ============================================
    echo.

    echo [1/4] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        echo Please ensure Python has venv module installed.
        pause
        exit /b 1
    )

    echo [2/4] Upgrading pip...
    "%VENV_PYTHON%" -m pip install --upgrade pip --quiet

    echo [3/4] Installing required packages...
    if exist "%REQUIREMENTS%" (
        "%VENV_PIP%" install -r "%REQUIREMENTS%" --quiet
    ) else (
        echo Installing fallback dependency set...
        "%VENV_PIP%" install requests pillow rich tkinterdnd2 selenium webdriver-manager --quiet
    )

    if %errorlevel% neq 0 (
        echo ERROR: Failed to install required packages.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )

    echo [4/4] Verifying installation...
    "%VENV_PYTHON%" -c "import requests, PIL, rich, tkinterdnd2" >nul 2>&1
    if %errorlevel% neq 0 (
        echo WARNING: Some packages may not have installed correctly.
        echo Attempting to reinstall tkinterdnd2...
        "%VENV_PIP%" install --force-reinstall tkinterdnd2 --quiet
    )

    echo.
    echo ============================================
    echo   Setup complete! Virtual environment ready.
    echo ============================================
    echo.
) else (
    "%VENV_PYTHON%" -c "import requests, PIL, rich" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Reinstalling missing packages...
        if exist "%REQUIREMENTS%" (
            "%VENV_PIP%" install -r "%REQUIREMENTS%" --quiet
        ) else (
            "%VENV_PIP%" install requests pillow rich tkinterdnd2 selenium webdriver-manager --quiet
        )
    )

    "%VENV_PYTHON%" -c "import tkinterdnd2" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Installing tkinterdnd2 for drag-drop support...
        "%VENV_PIP%" install tkinterdnd2 --quiet
    )
)

echo Starting Kling UI...
echo.
"%VENV_PYTHON%" -u "%SCRIPT_PATH%"
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% neq 0 (
    echo ============================================
    echo   APPLICATION CRASHED ^(Exit code: %EXIT_CODE%^)
    echo ============================================
    echo.
    echo Review the messages above for details.
    echo.
)
echo Press any key to close this window...
pause >nul

if exist "%BATCH_DIR%nul" del /f /q "%BATCH_DIR%nul" 2>nul

endlocal
