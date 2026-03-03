# Kling UI

AI media generation toolkit: face cropping, portrait analysis, selfie generation, image outpainting, and batch video creation — all from one GUI.

![Kling UI](kling_ui_preview.png)

## Quick Start (Windows)

1. Install [Python 3.10+](https://python.org) (enable "Add Python to PATH")
2. Double-click **`run_gui.bat`** — it creates a venv and installs dependencies automatically
3. Enter your API keys in the GUI settings

Or manually:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -c "from kling_gui import KlingGUIWindow; KlingGUIWindow().run()"
```

A CLI menu is also available via `python kling_automation_ui.py` (option 6 launches the GUI).

## The 5 Tabs

| Tab | What it does |
|-----|-------------|
| **Face Crop** | Extract 3:4 passport-style face crops using RetinaFace detection |
| **Prep** | Analyze portraits with vision AI (OpenRouter) to extract traits for prompt generation |
| **Selfie** | Generate AI selfies from identity reference photos via fal.ai (FLUX PuLID, Instant Character) or BFL (Kontext Pro/Max) |
| **Outpaint** | Expand images using fal.ai outpaint (pixel or percentage mode) |
| **Video** | Batch video generation from images — 13+ models including Kling 3.0, Hunyuan, MiniMax |

Images flow through the pipeline: input → crop → analyze → generate selfie → outpaint → animate as video.

## API Keys

| Provider | What for | Get one at |
|----------|----------|-----------|
| [fal.ai](https://fal.ai) | Video generation, selfie models, outpainting | fal.ai dashboard |
| [Freeimage.host](https://freeimage.host) | Image hosting (fal.ai requires public URLs) | freeimage.host/page/api |
| [BFL](https://api.bfl.ai) | FLUX Kontext / FLUX 2 Pro selfie models | api.bfl.ai |
| [OpenRouter](https://openrouter.ai) | Vision analysis in Prep tab | openrouter.ai/keys |

Only fal.ai + Freeimage.host are needed for basic video generation. The others unlock additional tabs.

## Output

Generated files go to `gen-images/` subfolders by default (created inside the source image's directory). Videos are named:

```
{imagename}_kling_{model_short}_{pN}.mp4
```

For example: `portrait_kling_k3pro_p2.mp4`

## Build Standalone EXE

```powershell
build_gui_exe.bat
```

Uses PyInstaller to produce a portable `dist/KlingUI/` folder. Requires `tkinterdnd2` installed in the build environment.

## Requirements

- Python 3.10+
- `requests`, `Pillow`, `rich`, `tkinterdnd2`, `deepface`
- Optional: `selenium`, `webdriver-manager` (balance tracking)
- Optional: `opencv-python`, `retinaface` (Face Crop tab)
- Optional: FFmpeg on PATH (video looping)

## License

Private project — not for redistribution.
