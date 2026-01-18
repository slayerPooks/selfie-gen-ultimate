# Project Structure

This document describes the file organization and module boundaries of the Kling UI project.

## Directory Tree

```
kling_ui_complete_2/
    kling_automation_ui.py      # CLI entry point (~61KB, 1150+ lines)
    kling_generator_falai.py    # Core API client (~38KB, 777 lines)
    path_utils.py               # Path utilities for PyInstaller (~3KB)
    dependency_checker.py       # Package verification (~15KB)
    balance_tracker.py          # Background balance monitoring (~7KB)
    selenium_balance_checker.py # Chrome automation (~10KB)
    requirements.txt            # Python dependencies
    kling_gui/                  # GUI package (~149KB total)
        __init__.py             # Package exports
        main_window.py          # Main Tkinter window (~42KB)
        config_panel.py         # Settings panel (~61KB)
        queue_manager.py        # Thread-safe queue (~23KB)
        drop_zone.py            # Drag-and-drop widget (~12KB)
        log_display.py          # Color-coded log (~4KB)
        video_looper.py         # FFmpeg wrapper (~6KB)
    distribution/               # Standalone distribution
        gui_launcher.py         # PyInstaller entry point
        run_kling_ui.bat        # Auto-venv setup launcher
    docs/                       # Documentation
        Home.md, Installation.md, Usage.md
        Architecture.md, Configuration.md
        Troubleshooting.md, Structure.md
    [generated files]
        kling_config.json       # User configuration (auto-generated)
        kling_history.json      # Generation history
        kling_automation.log    # CLI log file
        kling_gui.log           # GUI log file
```

## Module Boundaries

### Core Layer (Root)

| File | Responsibility | Dependencies |
|------|----------------|--------------|
| kling_generator_falai.py | fal.ai API integration, image upload, video download | requests, PIL |
| kling_automation_ui.py | CLI menu system, user interaction | rich, kling_generator_falai |
| path_utils.py | PyInstaller path resolution | None (stdlib only) |
| dependency_checker.py | Package verification and installation | subprocess, importlib |

### GUI Package (kling_gui/)

| Module | Responsibility | Key Classes |
|--------|----------------|-------------|
| main_window.py | Window assembly, event routing | KlingGUIWindow |
| config_panel.py | Settings UI, model fetching | ConfigPanel, PromptEditorDialog |
| queue_manager.py | Thread-safe processing queue | QueueManager, QueueItem |
| drop_zone.py | Drag-and-drop widget | DropZone |
| log_display.py | Scrolling log with colors | LogDisplay |
| video_looper.py | FFmpeg ping-pong effect | create_looped_video() |

## Key File Locations

### Entry Points
- **CLI Mode**: `kling_automation_ui.py` (run directly)
- **GUI Mode**: `kling_gui/main_window.py` -> `launch_gui()`
- **Distribution**: `distribution/gui_launcher.py` (PyInstaller entry)

### Configuration
- **Runtime Config**: `kling_config.json` (auto-generated)
- **Generation History**: `kling_history.json`
- **Chrome Profile**: `chrome_profile/` (Selenium persistence)

### Logs
- **CLI Log**: `kling_automation.log`
- **GUI Log**: `kling_gui.log`

## Naming Conventions

### Files
- **Snake case**: `kling_generator_falai.py`
- **Suffix patterns**:
  - `_ui.py` → User interface modules
  - `_checker.py` → Verification/monitoring modules
  - `_tracker.py` → Background monitoring wrappers

### Classes
- **PascalCase**: `KlingGUIWindow`, `QueueManager`, `ConfigPanel`
- **Suffixes**:
  - `Window` → Top-level Tkinter windows
  - `Panel` → Embedded UI sections
  - `Manager` → Background service coordinators
  - `Dialog` → Modal popup windows

### Output Files
- **Video naming**: `{imagename}_kling_{model}_{pN}.mp4`
  - Example: `selfie_kling_k25turbo_p2.mp4`
  - Model short names: k25turbo, k25, k21pro, k21master, kO1, wan25, veo3, ovi, ltx2, pix5
  - pN = prompt slot number (p1, p2, p3)

### Configuration Keys
- **Snake case** in JSON: `falai_api_key`, `output_folder`, `current_model`
- **Boolean flags**: `use_source_folder`, `loop_videos`, `allow_reprocess`

## Import Structure

```python
# Core application imports
from kling_generator_falai import FalAIKlingGenerator
from path_utils import get_resource_path, get_config_path

# GUI imports
from kling_gui import KlingGUIWindow
from kling_gui.queue_manager import QueueManager, QueueItem
from kling_gui.config_panel import ConfigPanel
from kling_gui.drop_zone import DropZone
from kling_gui.log_display import LogDisplay
from kling_gui.video_looper import create_looped_video
```

## File Size Reference

| File | Lines | Size | Complexity |
|------|-------|------|------------|
| kling_automation_ui.py | ~1150 | 61KB | High |
| config_panel.py | ~1367 | 61KB | High |
| main_window.py | ~1131 | 42KB | Medium |
| kling_generator_falai.py | ~777 | 38KB | High |
| queue_manager.py | ~572 | 23KB | Medium |
| dependency_checker.py | ~422 | 15KB | Low |
| drop_zone.py | ~357 | 12KB | Low |
| selenium_balance_checker.py | ~288 | 10KB | Medium |
| video_looper.py | ~197 | 6KB | Low |
| balance_tracker.py | ~177 | 7KB | Low |
| log_display.py | ~113 | 4KB | Low |
| path_utils.py | ~101 | 3KB | Low |
