@echo off
setlocal enabledelayedexpansion

set "BATCH_DIR=%~dp0"
set "GUI_SCRIPT=%BATCH_DIR%gui_launcher.py"
set "VENV_DIR=%BATCH_DIR%venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS=%BATCH_DIR%requirements.txt"

if exist "%VENV_PYTHON%" goto :launch

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

echo  Installing dependencies from requirements.txt...
echo.
"%VENV_PYTHON%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PYTHON%" -m pip install --only-binary :all: -r "%REQUIREMENTS%"
if !errorlevel! neq 0 (
    echo.
    echo  Retrying without binary constraint...
    "%VENV_PYTHON%" -m pip install -r "%REQUIREMENTS%"
)

echo.
echo  Installing optional face analysis dependencies...
"%VENV_PYTHON%" -m pip install retina-face >nul 2>&1

echo.
echo  Setup complete!
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
