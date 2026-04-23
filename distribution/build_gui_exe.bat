@echo off
setlocal

:: ============================================================
::  Kling UI - Build Direct GUI Executable
::  Creates a standalone .exe that launches Tkinter GUI directly
::  (bypasses CLI menu system)
::
::  SECURITY IMPROVEMENTS:
::  - Does NOT copy .py files externally (prevents code hijacking)
::  - All code bundled internally by PyInstaller
::  - UPX disabled to avoid AV false positives
:: ============================================================

echo.
echo ============================================
echo   Kling UI - Build Direct GUI Launcher
echo   (Hardened Build)
echo ============================================
echo.

:: Get script directory
set SCRIPT_DIR=%~dp0

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

:: Check/install PyInstaller
echo [1/4] Checking PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

:: Install dependencies needed for build
echo [2/4] Installing build dependencies...
python -m pip install requests Pillow rich tkinterdnd2 selenium webdriver-manager --quiet

:: Clean previous builds
echo [3/4] Cleaning previous builds...
if exist "%SCRIPT_DIR%build" rmdir /s /q "%SCRIPT_DIR%build"
if exist "%SCRIPT_DIR%dist\KlingGUI_Direct" rmdir /s /q "%SCRIPT_DIR%dist\KlingGUI_Direct"

:: Build the executable
echo [4/4] Building GUI executable...
echo.
cd /d "%SCRIPT_DIR%"
python -m pyinstaller kling_gui_direct.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   BUILD FAILED
    echo ============================================
    echo Check the errors above for details.
    pause
    exit /b 1
)

:: Create a README for the distribution
echo.
echo Creating distribution README...
echo Kling UI - Direct GUI Launcher > "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo This executable launches the Tkinter GUI directly. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo No CLI menu - just drag and drop images to generate videos! >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo Double-click KlingGUI_Direct.exe to start. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo First run will prompt for fal.ai API key. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo Configuration saved in kling_config.json. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo SECURITY NOTE: All code is bundled internally. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"
echo Do NOT add .py files to this directory - they will be ignored. >> "%SCRIPT_DIR%dist\KlingGUI_Direct\README.txt"

echo.
echo ============================================
echo   BUILD SUCCESSFUL!
echo ============================================
echo.
echo Output location: %SCRIPT_DIR%dist\KlingGUI_Direct\
echo.
echo Files created:
echo   - KlingGUI_Direct.exe (main executable)
echo   - _internal\ (bundled dependencies)
echo   - README.txt (usage instructions)
echo.
echo To distribute:
echo   1. Copy the entire 'dist\KlingGUI_Direct' folder
echo   2. Users run KlingGUI_Direct.exe
echo   3. No external .py files needed (all bundled)
echo.
echo SECURITY FEATURES:
echo   - All code bundled internally (prevents tampering)
echo   - UPX disabled (reduces AV false positives)
echo   - No external module loading (secure by default)
echo.
echo NOTE: First run will create kling_config.json for settings
echo.

:: Open the output folder
explorer "%SCRIPT_DIR%dist\KlingGUI_Direct"

pause
endlocal
