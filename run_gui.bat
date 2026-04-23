@echo off
setlocal enabledelayedexpansion

set "BATCH_DIR=%~dp0"
set "GUI_SCRIPT=%BATCH_DIR%gui_launcher.py"
set "VENV_DIR=%BATCH_DIR%venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS=%BATCH_DIR%requirements.txt"
set "OLDCAM_REQUIREMENTS=%BATCH_DIR%oldcam-v7\requirements.txt"

if not exist "%VENV_PYTHON%" (
    echo.
    echo  Creating virtual environment...
    echo.
    python -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo.
        echo  ERROR: Failed to create venv. Is Python installed and on PATH?
        echo.
        pause
        exit /b 1
    )
    echo  venv created.
    echo.
)

echo.
echo  Syncing dependencies from requirements.txt...
echo.
"%VENV_PYTHON%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PYTHON%" -m pip install --only-binary :all: -r "%REQUIREMENTS%"
if !errorlevel! neq 0 (
    echo.
    echo  Retrying base dependencies without binary constraint...
    "%VENV_PYTHON%" -m pip install -r "%REQUIREMENTS%"
)

if exist "%OLDCAM_REQUIREMENTS%" (
    echo.
    echo  Syncing Oldcam dependencies...
    "%VENV_PYTHON%" -m pip install --only-binary :all: -r "%OLDCAM_REQUIREMENTS%"
    if !errorlevel! neq 0 (
        echo  Retrying Oldcam dependencies without binary constraint...
        "%VENV_PYTHON%" -m pip install -r "%OLDCAM_REQUIREMENTS%"
        if !errorlevel! neq 0 (
            echo.
            echo  WARNING: Oldcam dependencies failed to install after retry.
            echo  WARNING: Oldcam Finish may not work correctly.
            echo.
        ) else (
            echo  Oldcam dependencies installed on retry.
        )
    )
)

echo.
echo  Dependency sync complete.
echo.

:launch
echo Using venv: %VENV_PYTHON%
echo Starting Kling UI GUI...
echo.

"%VENV_PYTHON%" -u "%GUI_SCRIPT%"
set "EXIT_CODE=!errorlevel!"

echo.
if !EXIT_CODE! neq 0 (
    echo  CRASH - exit code: !EXIT_CODE!
    echo  Check crash_log.txt for details.
    echo.
)

echo Press any key to close...
pause >nul
endlocal
