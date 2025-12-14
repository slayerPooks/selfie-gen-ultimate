# Kling UI - Video Generation Tool

A self-contained UI tool for batch video generation using Kling AI via fal.ai API.

## Quick Start

1. **Double-click `run_kling_ui.bat`** to launch
2. **First Run**: Automatically creates a virtual environment and installs dependencies (~60 seconds)
3. **Enter API Key**: On first launch, enter your fal.ai API key (saved for future use)
4. **Configure**: Select input/output folders and start generating videos

## Requirements

- **Python 3.8+** - Must be installed and in PATH
- **Internet connection** - For API calls and package installation
- **fal.ai API key** - Get one from https://fal.ai

**That's it!** All Python packages are auto-installed to a local `venv/` folder.

## First Run Setup

On first launch, the batch file automatically:
```
============================================
  First-time setup: Creating virtual environment...
============================================

[1/3] Creating virtual environment...
[2/3] Upgrading pip...
[3/3] Installing required packages...

============================================
  Setup complete! Virtual environment ready.
============================================
```

This only happens once. Subsequent runs start instantly.

## Included Files

```
distribution/
├── run_kling_ui.bat           # Launcher (double-click to run)
├── kling_automation_ui.py     # Main UI script
├── kling_generator_falai.py   # Kling generator with fal.ai API
├── balance_tracker.py         # Real-time balance tracking
├── selenium_balance_checker.py # Balance checker module
├── requirements.txt           # Python dependencies
├── venv/                      # Created automatically on first run
└── kling_config.json          # Created on first run (stores settings)
```

## First Run Setup

On first launch, you'll be prompted to enter your fal.ai API key:
```
============================================
  KLING UI - First Time Setup
============================================

Welcome! To use this tool, you need a fal.ai API key.

To get your API key:
  1. Go to https://fal.ai
  2. Create an account or sign in
  3. Navigate to your API keys section
  4. Create and copy your API key
```

Your API key is saved to `kling_config.json` and persists between sessions.

## Configuration

Settings stored in `kling_config.json`:
- fal.ai API key (entered on first run)
- Output folder path
- Input folder with source images
- Prompt templates (3 slots, 2 pre-configured)
- Model selection (default: Kling 2.5 Turbo Pro)

## Features

- **Batch Processing**: Generate videos from multiple images
- **Concurrent Generation**: Process 5 videos simultaneously
- **Duplicate Detection**: Avoid regenerating existing videos
- **Real-time Progress**: Rich console UI with progress tracking
- **Custom Prompts**: 3 saveable prompt slots
- **Balance Tracking**: Monitor fal.ai API credits (optional)

## Python Dependencies

Automatically installed to local venv:
- `requests` - HTTP client for API calls
- `Pillow` - Image processing
- `rich` - Beautiful console UI
- `selenium` - Browser automation (for balance tracking)
- `webdriver-manager` - Automatic ChromeDriver management

## Troubleshooting

- **"Python not found"**: Install Python 3.8+ and check "Add to PATH"
- **"Failed to create venv"**: Ensure Python's venv module is available
- **API errors**: Check your fal.ai API key is valid
- **Balance tracking fails**: This feature is optional, can be disabled in UI

## Cost

Kling 2.5 Turbo Pro: ~$0.45 per 10-second video via fal.ai API

## Distribution

This folder is **100% self-contained**. To share:
1. Zip the entire folder (excluding `venv/` and `kling_config.json` to save space)
2. Recipients only need Python 3.8+ installed
3. Virtual environment and config are auto-created on first run

### To Clean for Distribution
```cmd
rmdir /s /q venv
del kling_config.json
```
