@echo off
setlocal

:: ============================================================
::  Kling UI - Build Executable
::  Creates a standalone .exe using PyInstaller
:: ============================================================

echo.
echo ============================================
echo   Kling UI - Build Executable
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
if exist "%SCRIPT_DIR%dist\KlingUI" rmdir /s /q "%SCRIPT_DIR%dist\KlingUI"

:: Build the executable
echo [4/4] Building executable...
echo.
cd /d "%SCRIPT_DIR%"
python -m pyinstaller kling_ui.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   BUILD FAILED
    echo ============================================
    echo Check the errors above for details.
    pause
    exit /b 1
)

:: SECURITY: Do NOT copy external .py files next to the executable.
:: All code must be bundled internally by PyInstaller.

:: Create a launcher batch file for the built exe
echo @echo off > "%SCRIPT_DIR%dist\KlingUI\Run_KlingUI.bat"
echo cd /d "%%~dp0" >> "%SCRIPT_DIR%dist\KlingUI\Run_KlingUI.bat"
echo start "" "KlingUI.exe" >> "%SCRIPT_DIR%dist\KlingUI\Run_KlingUI.bat"

echo.
echo ============================================
echo   BUILD SUCCESSFUL!
echo ============================================
echo.
echo Output location: %SCRIPT_DIR%dist\KlingUI\
echo.
echo Files created:
echo   - KlingUI.exe (main executable)
echo   - Run_KlingUI.bat (launcher)
echo.
echo To distribute:
echo   1. Copy the entire 'dist\KlingUI' folder
echo   2. Users run KlingUI.exe or Run_KlingUI.bat
echo.
echo NOTE: First run will create kling_config.json for settings
echo.

:: Open the output folder
explorer "%SCRIPT_DIR%dist\KlingUI"

pause
endlocal
