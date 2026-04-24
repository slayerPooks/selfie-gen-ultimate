@echo off
setlocal enabledelayedexpansion

set "BATCH_DIR=%~dp0"
set "VENV_PYTHON=%BATCH_DIR%venv\Scripts\python.exe"
set "OLDCAM_LAUNCHER=%BATCH_DIR%oldcam-v7\launcher.py"
set "OLDCAM_REQUIREMENTS=%BATCH_DIR%oldcam-v7\requirements.txt"

if not exist "%OLDCAM_LAUNCHER%" (
    echo ERROR: Missing Oldcam launcher at:
    echo   %OLDCAM_LAUNCHER%
    pause
    exit /b 1
)

set "PYTHON_EXE="
set "PYTHON_ARGS="

if exist "%VENV_PYTHON%" (
    set "PYTHON_EXE=%VENV_PYTHON%"
)

if not defined PYTHON_EXE (
    where py >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON_EXE (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE (
    echo ERROR: Python not found. Install Python or create .\venv first.
    pause
    exit /b 1
)

echo Using Python: %PYTHON_EXE% %PYTHON_ARGS%
if exist "%OLDCAM_REQUIREMENTS%" (
    echo Syncing Oldcam dependencies...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r "%OLDCAM_REQUIREMENTS%" >nul 2>&1
    if !errorlevel! neq 0 (
        echo WARNING: Could not auto-install all Oldcam dependencies.
    )
)

echo Launching Oldcam V7...
"%PYTHON_EXE%" %PYTHON_ARGS% -u "%OLDCAM_LAUNCHER%" %*
set "EXIT_CODE=!errorlevel!"

echo.
if !EXIT_CODE! neq 0 (
    echo Oldcam exited with code: !EXIT_CODE!
)

if not defined OLDCAM_NO_PAUSE (
    echo Press any key to close...
    pause >nul
)
endlocal
exit /b %EXIT_CODE%
