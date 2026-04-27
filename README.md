# Kling UI

AI media generation toolkit for face cropping, portrait analysis, selfie generation, image expansion/outpainting, and batch video creation from one GUI.

![Kling UI](kling_ui_preview.png)

## What It Does

| Tab | Purpose |
| --- | --- |
| Face Crop | Extract 3:4 face crops and prepare portrait inputs |
| Prep | Analyze portraits with OpenRouter vision models and build prompt material |
| Selfie | Generate identity-based selfies with fal.ai and BFL models |
| Expand / Outpaint | Expand images with fal.ai/BFL workflows |
| Video | Batch image-to-video generation across supported fal.ai video models |

Images move through the pipeline: input -> crop -> prep -> selfie -> expand/outpaint -> video.

## Quick Start: Windows

1. Install Python 3.10+ from [python.org](https://python.org) and enable **Add Python to PATH**.
2. Double-click `run_gui.bat`.
3. Enter API keys in GUI settings.

Manual launch:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python gui_launcher.py
```

The CLI menu is available with:

```powershell
python kling_automation_ui.py
```

## Quick Start: macOS

macOS needs Python 3.11+ with Tk support. The mac launchers prefer a Tk-capable interpreter and create `.venv-macos` automatically.

Run setup once, or whenever dependencies change:

```bash
./setup_macos.sh
```

Launch GUI from Terminal:

```bash
./run_gui.sh
```

Launch CLI from Terminal:

```bash
./run_cli.sh
```

Finder-friendly launchers:

- `run_gui.command`: opens the GUI
- `run_kling_ui.command`: GUI alias for users expecting the app name
- `run_cli.command`: opens the CLI menu

If macOS Gatekeeper blocks a `.command` file, right-click it, choose **Open**, then confirm once.

If execute permissions are lost:

```bash
chmod +x setup_macos.sh run_gui.sh run_gui.command run_kling_ui.sh run_kling_ui.command run_cli.sh run_cli.command
```

## macOS Python And Tk

The GUI requires `tkinter`. If Homebrew Python lacks Tk, install the matching package, then rerun setup:

```bash
brew install python@3.11 python-tk@3.11
./setup_macos.sh
```

The python.org macOS installer usually includes Tk already. You can force a specific interpreter with:

```bash
KLING_PYTHON=/path/to/python3.11 ./setup_macos.sh
```

## API Keys

| Provider | Unlocks | Required for |
| --- | --- | --- |
| fal.ai | Video, selfie, expand/outpaint models | Most generation flows |
| Freeimage.host | Public image URLs for fal.ai workflows | Upload-dependent fal.ai flows |
| BFL | FLUX Kontext / FLUX 2 selfie models | BFL selfie and image tools |
| OpenRouter | Vision analysis | Prep tab |

The app can start without keys. Missing, rejected, or rate-limited keys should appear as targeted status messages instead of generic startup crashes.

## Outputs And User Data

Generated media still goes to `gen-images/` or `gen-videos/` near the source image. The path helpers avoid nesting generated folders when outputs are reused across tabs.

Runtime data locations:

- Windows: portable app-local files remain the default, matching the tested Windows workflow.
- macOS: config, logs, crash reports, model cache, and sessions live under `~/Library/Application Support/selfie-gen-ultimate/`.

## Dependency Checks

Check installed packages and external tools:

```bash
python dependency_checker.py
```

Check and optionally repair the runtime face stack:

```bash
python dependency_health_check.py --mode check
python dependency_health_check.py --mode repair
```

`tensorflow-intel` repair is Windows-only. macOS uses the normal TensorFlow package path.

## Build Standalone Windows EXE

```powershell
build_gui_exe.bat
```

This uses PyInstaller to produce a portable `dist/KlingUI/` folder. `tkinterdnd2` must be available in the build environment.

## Requirements

- Python 3.10+ on Windows
- Python 3.11+ with Tk on macOS
- `requests`, `Pillow`, `rich`, `tkinterdnd2`
- Face tools: `opencv-python-headless`, `retina-face`, `deepface`, `tf-keras`
- Optional: `selenium`, `webdriver-manager` for balance/browser workflows
- Optional: FFmpeg on PATH for video looping

## Troubleshooting

- GUI fails immediately on macOS: run `./setup_macos.sh` and confirm `python -c "import tkinter"` works in `.venv-macos`.
- Drag/drop unavailable: install or repair `tkinterdnd2`; file picker fallback remains usable.
- Model list fails: check fal.ai key, account status, and rate limits. Cached metadata remains usable when available.
- Face crop/prep fails: run `python dependency_health_check.py --mode check` to find broken TensorFlow/RetinaFace imports.
- API generation fails: verify provider credits and API keys in settings.

## License

Private project - not for redistribution.
