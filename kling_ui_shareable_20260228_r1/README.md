# Kling UI (Shareable Build)

This package is prepared for sharing with a colleague on a different machine.

## First Run (Windows)
1. Install Python 3.8+ from https://python.org (enable "Add Python to PATH").
2. Extract this zip.
3. Double-click `run_kling_ui.bat`.

The launcher will automatically:
- Create a local virtual environment (`venv/`)
- Install dependencies from `requirements.txt`
- Start the CLI app

## Manual Run
```powershell
python -m venv venv
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python kling_automation_ui.py
```

## Important
- API key is not bundled. The app will prompt for a `fal.ai` key on first run.
- `FFmpeg` is optional (used for looped video feature).
- GUI mode is available from menu option `6`.

## Optional: Build Standalone GUI EXE
If you want a Python-free handoff, this package also includes:
- `gui_launcher.py`
- `kling_gui_direct.spec`
- `build_gui_exe.bat`
- `hooks/hook-tkinterdnd2.py`

Run `build_gui_exe.bat` to generate a `KlingGUI_Direct.exe` distribution folder.

## Included
- `kling_automation_ui.py` (CLI entry)
- `kling_gui/` (GUI package)
- `kling_generator_falai.py` (fal.ai integration)
- `run_kling_ui.bat` (auto setup launcher)
- `dependency_checker.py` (dependency diagnostics)
