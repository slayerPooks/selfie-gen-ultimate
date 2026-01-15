# Technology Stack

**Analysis Date:** 2026-01-14

## Languages

**Primary:**
- Python 3.8+ - All application code

**Secondary:**
- None - Pure Python project

## Runtime

**Environment:**
- Python 3.8+ (minimum requirement per `CLAUDE.md`)
- Platform: Windows primary with cross-platform fallbacks
- No virtual environment configuration file detected

**Package Manager:**
- pip - Standard Python package manager
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- Tkinter - Native Python GUI framework (`kling_gui/main_window.py`)
- Rich - Terminal UI with progress bars and panels (`kling_automation_ui.py`)
- tkinterdnd2 - Drag-and-drop extension for Tkinter (`kling_gui/drop_zone.py`)

**Testing:**
- None detected - No test framework configured

**Build/Dev:**
- None - No build tooling (pure Python interpreted)

## Key Dependencies

**Critical:**
- requests - HTTP library for fal.ai API calls (`kling_generator_falai.py`)
- Pillow - Image processing, resize, format conversion (`kling_generator_falai.py`)
- rich - Terminal UI with colored output (`kling_automation_ui.py`)

**Optional:**
- selenium - Browser automation for balance tracking (`selenium_balance_checker.py`)
- webdriver-manager - Automatic ChromeDriver management (`selenium_balance_checker.py`)
- tkinterdnd2 - Drag-and-drop support for GUI (`kling_gui/drop_zone.py`)

**External Tools:**
- FFmpeg - Video looping/ping-pong effect (optional, `kling_gui/video_looper.py`)

## Configuration

**Environment:**
- No .env file support
- Configuration via JSON files (`kling_config.json`)
- API key stored in config JSON (not environment variables)

**Build:**
- No build configuration (interpreted Python)
- `requirements.txt` for dependency management

## Platform Requirements

**Development:**
- Windows, macOS, or Linux with Python 3.8+
- Optional: Chrome browser for balance tracking
- Optional: FFmpeg for video looping feature

**Production:**
- Distributed as Python scripts
- Users install dependencies via pip
- Self-contained distribution folder available (`distribution/`)

---

*Stack analysis: 2026-01-14*
*Update after major dependency changes*
