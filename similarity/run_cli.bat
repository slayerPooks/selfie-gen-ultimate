@echo off
setlocal enabledelayedexpansion

:: Change to the directory of this script
cd /d "%~dp0"

:: Select a supported Python interpreter for TensorFlow/DeepFace CLI mode
set "PYTHON_BIN="
for %%P in (python3.12 python3.11 python3.10 python3.9 python3 python) do (
    %%P -c "import sys; raise SystemExit(0 if ((3,9) <= sys.version_info[:2] <= (3,12)) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_BIN=%%P"
        goto :python_found
    )
)

:python_found
if "%PYTHON_BIN%"=="" (
    echo [ERROR] No supported Python found (requires 3.9-3.12 for TensorFlow/DeepFace).
    echo Install Python 3.12 and retry.
    pause
    exit /b 1
)

echo [INFO] Using Python interpreter: %PYTHON_BIN%
set TF_USE_LEGACY_KERAS=1
set KERAS_BACKEND=tensorflow

:: Check if .venv exists
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Virtual environment not found. Creating one...
    %PYTHON_BIN% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    .venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if ((3,9) <= sys.version_info[:2] <= (3,12)) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Existing virtual environment uses unsupported Python. Recreating...
        rmdir /s /q .venv
        %PYTHON_BIN% -m venv .venv
        if errorlevel 1 (
            echo [ERROR] Failed to recreate virtual environment.
            pause
            exit /b 1
        )
    ) else (
        echo [INFO] Activating existing virtual environment...
    )
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Synchronizing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to synchronize dependencies from requirements.txt.
    pause
    exit /b 1
)

:: Run the application
echo [INFO] Launching Face Similarity CLI...
python main.py --cli

echo.
echo [INFO] Application finished.
pause
endlocal
