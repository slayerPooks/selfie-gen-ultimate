# Kling UI Complete Package

## What's Included
- run_kling_ui.bat - Main launcher
- kling_automation_ui.py - Main UI script
- kling_generator_falai.py - Kling generator with fal.ai API
- balance_tracker.py - Real-time balance tracking
- selenium_balance_checker.py - Balance checker module
- kling_config.json - Configuration file (auto-generated on first run)

## Requirements
- Python 3.8+ (with pip)
- Required Python packages:
  pip install requests pillow rich selenium

## How to Use
1. Extract all files to a folder (e.g., C:\KlingUI\)
2. Install Python dependencies (see Requirements above)
3. Double-click run_kling_ui.bat to launch
4. On first run, configure:
   - fal.ai API key
   - Output folder path
   - Input folder with GenX images

## Configuration
The UI will guide you through setup on first launch.
Settings are saved in kling_config.json for future use.

## API Key
You'll need a fal.ai API key. The current key in the config:
d437502e-73a8-49f0-87be-c78cb78e5018:98209ef8ae2b312a3f4bc14ddedf8f1a

## Features
- Batch video generation from GenX images
- Concurrent processing (5 videos at once)
- Duplicate detection
- Real-time progress with Rich UI
- Custom prompt support
- Verbose logging option

## Troubleshooting
- If balance tracking fails, disable it in the UI (it's optional)
- Make sure Python is in your PATH
- Check that all dependencies are installed
- For balance tracking, Chrome profile will be created automatically

## Cost
Kling 2.1 Professional: .90 per 10-second video via fal.ai API
