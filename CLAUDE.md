# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kling UI is a batch video generation tool using fal.ai Platform API to create AI videos from images. It provides:
- **CLI Mode**: Terminal-based Rich UI menu system
- **GUI Mode**: Tkinter drag-and-drop interface with queue management
- **Balance Tracking**: Optional real-time fal.ai credit monitoring via Selenium

## Commands

```bash
# Run CLI application
python kling_automation_ui.py

# Launch GUI directly
python -c "from kling_gui import KlingGUIWindow; KlingGUIWindow().run()"

# Check dependencies
python dependency_checker.py

# Test balance checker (opens Chrome for login)
python selenium_balance_checker.py

# Install dependencies
pip install requests pillow rich selenium webdriver-manager tkinterdnd2
```

## Architecture

### Core Files

| File | Purpose |
|------|---------|
| `kling_automation_ui.py` | CLI menu system (`KlingAutomationUI` class) |
| `kling_generator_falai.py` | fal.ai API integration with progress callbacks |
| `dependency_checker.py` | Checks/installs Python packages and external tools |
| `kling_config.json` | Persistent configuration (auto-generated) |

### Balance Tracking System

| File | Class | Purpose |
|------|-------|---------|
| `selenium_balance_checker.py` | `SeleniumBalanceChecker` | Chrome automation to read fal.ai balance page |
| `balance_tracker.py` | `RealTimeBalanceTracker` | Background thread wrapper with callbacks |

Balance tracking uses a persistent Chrome profile (`chrome_profile/`) to save login session. First run requires manual login; subsequent runs use saved session in headless mode.

### GUI Package (`kling_gui/`)

| Module | Class | Purpose |
|--------|-------|---------|
| `main_window.py` | `KlingGUIWindow` | Main Tkinter window, assembles all components |
| `config_panel.py` | `ConfigPanel` | Model/output/prompt settings + verbose toggle |
| `config_panel.py` | `PromptEditorDialog` | Modal dialog for editing prompts |
| `queue_manager.py` | `QueueManager` | Thread-safe processing queue with worker thread |
| `queue_manager.py` | `QueueItem` | Dataclass for queue items with status tracking |
| `drop_zone.py` | `DropZone` | Drag-and-drop + click-to-browse widget (tkinterdnd2) |
| `log_display.py` | `LogDisplay` | Color-coded scrolling log widget with verbose tags |
| `video_looper.py` | `create_looped_video()` | FFmpeg ping-pong loop effect |

### Distribution Package (`distribution/`)

Self-contained distribution folder with auto-venv setup:
- `run_kling_ui.bat` - Auto-creates venv and installs deps on first run
- Complete source files for standalone deployment
- Recipients only need Python 3.8+ installed

### CLI Menu Options

1. Set API Key
2. Set Output Folder
3. Process Single File
4. Process Folder
5. View/Edit Configuration
6. **Launch GUI** → Opens `KlingGUIWindow`
7. **Check Dependencies** → Runs `dependency_checker.py`

### Data Flow

```
Image → freeimage.host upload → fal.ai queue API → Poll status → Download video
```

1. Images uploaded to freeimage.host (fal.ai requires public URLs)
2. fal.ai queue API returns `request_id` and `status_url`
3. Polling with exponential backoff (5s → 10s → 15s)
4. Video downloaded as `{imagename}_kling_{model}_{pN}.mp4` (e.g., `selfie_kling_k25turbo_p2.mp4`)

### Configuration Schema (`kling_config.json`)

```json
{
  "falai_api_key": "",
  "output_folder": "",
  "use_source_folder": true,
  "current_model": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
  "model_display_name": "Kling 2.5 Turbo Pro",
  "current_prompt_slot": 2,
  "saved_prompts": {"1": "...", "2": "...", "3": null},
  "video_duration": 10,
  "loop_videos": false,
  "allow_reprocess": true,
  "reprocess_mode": "increment",
  "verbose_logging": true,
  "verbose_gui_mode": false,
  "duplicate_detection": true
}
```

**Configuration Notes**:
- `output_folder`: Defaults to empty - user picks their own folder (saved between sessions)
- `verbose_gui_mode`: Enables detailed CLI-like output in GUI log panel
- **Default Prompts**: Slot 1 = basic head turn, Slot 2 = enhanced lifelike animation (recommended)

### Key Implementation Details

**Thread Safety** (`queue_manager.py`):
- `threading.Lock()` protects `items` list
- GUI updates via `root.after()` for thread-safe Tkinter calls
- Worker thread is daemon (stops on window close)

**Balance Tracker Threading** (`balance_tracker.py`):
- Headless Chrome runs in background daemon thread
- 30-second refresh interval by default
- Callbacks update UI via `set_callback()`
- Suppresses all Selenium/WebDriver logging to prevent console spam

**Verbose GUI Mode** (`config_panel.py`, `queue_manager.py`, `kling_generator_falai.py`):
- Toggle in config panel enables detailed logging
- Progress callback pattern: generator → queue_manager → log_display
- Color-coded message levels: upload, task, progress, debug, resize, download, api
- Displays: image resize info, upload progress, task IDs, polling status, download progress, file sizes, generation times

**Click-to-Browse** (`drop_zone.py`):
- Drop zone is clickable (in addition to drag-and-drop)
- Opens file dialog for image selection
- Supports multi-select with same file type validation

**Log Display Colors** (`log_display.py`):
```python
# Standard levels
"info": "#E0E0E0"       # Light gray
"success": "#00FF88"    # Bright green
"error": "#FF6B6B"      # Coral red
"warning": "#FFD93D"    # Yellow

# Verbose mode levels
"upload": "#00CED1"     # Dark cyan
"task": "#87CEEB"       # Sky blue
"progress": "#FFD700"   # Gold
"debug": "#808080"      # Gray
"resize": "#DDA0DD"     # Plum
"download": "#98FB98"   # Pale green
"api": "#DA70D6"        # Orchid
```

**Reprocessing Modes**:
- `allow_reprocess: false` → Skip existing videos
- `reprocess_mode: "overwrite"` → Delete and regenerate
- `reprocess_mode: "increment"` → Save as `_kling_{model}_pN_2.mp4`, `_kling_{model}_pN_3.mp4`

**Model Short Names in Filenames**:
- Kling 2.5 Turbo: `k25turbo`
- Kling 2.5: `k25`
- Kling 2.1 Pro: `k21pro`
- Kling 2.1 Master: `k21master`
- Kling O1: `kO1`
- Wan 2.5: `wan25`
- Veo 3: `veo3`
- Ovi: `ovi`
- LTX-2: `ltx2`
- Pixverse V5: `pix5`
- Hunyuan: `hunyuan`
- MiniMax: `minimax`

**Output Folder Fallback**:
- If custom output folder is empty/invalid and "Use Source Folder" is unchecked, falls back to source folder with warning

**Valid Image Extensions**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.gif`, `.tiff`, `.tif`

### API Endpoints

- **Queue**: `https://queue.fal.run/{model_endpoint}`
- **Models**: `https://api.fal.ai/v1/models?category=image-to-video`
- **Concurrency**: Max 5 parallel generations
- **Format**: 9:16 aspect ratio, 10 seconds duration
- **Cost**: ~$0.45-0.70 per 10-second video (varies by model)

### Progress Callback Pattern

The generator supports a progress callback for verbose GUI logging:

```python
# In queue_manager.py
def progress_callback(message: str, level: str = "info"):
    self.log_verbose(message, level)

if config.get("verbose_gui_mode", False):
    self.generator.set_progress_callback(progress_callback)

# In kling_generator_falai.py
def set_progress_callback(self, callback):
    """Set a callback for progress updates (used by GUI verbose mode)."""
    self._progress_callback = callback

def _report_progress(self, message: str, level: str = "info"):
    """Report progress to callback if set."""
    if self._progress_callback:
        self._progress_callback(message, level)

# Called at key points: resize, upload, task creation, polling, download
```

### Recent Changes (Dec 2024)

- **Empty Default Output Folder**: No longer pre-fills `~/Downloads` - starts blank, remembers user's choice
- **Verbose GUI Mode**: Checkbox toggle for detailed CLI-like output in GUI
- **Color-Coded Log Levels**: 7 additional color tags for verbose messages
- **Click-to-Browse**: Drop zone is clickable to open file explorer dialog
- **Progress Callbacks**: Generator reports detailed progress to GUI when verbose mode enabled
- **Fallback Logic**: Uses source folder when custom output folder is empty/invalid
