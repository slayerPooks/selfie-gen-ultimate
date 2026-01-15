# AGENTS.md - Kling UI Codebase Guide

> For AI coding agents working in this repository. Last updated: 2026-01-15

## Quick Reference

### Build/Run Commands

```bash
# Run CLI application (main entry point)
python kling_automation_ui.py

# Launch GUI directly
python -c "from kling_gui import KlingGUIWindow; KlingGUIWindow().run()"

# Check dependencies
python dependency_checker.py

# Test balance checker (opens Chrome for login)
python selenium_balance_checker.py
```

### Install Dependencies

```bash
pip install requests pillow rich selenium webdriver-manager tkinterdnd2
```

### Testing

**No automated test framework is configured.** Testing is manual:

```bash
# Manual CLI testing
python kling_automation_ui.py
# Navigate menu options, process test images

# Manual GUI testing  
python -c "from kling_gui import KlingGUIWindow; KlingGUIWindow().run()"
# Drag-and-drop images, verify queue processing
```

If adding tests, use pytest:
```bash
pip install pytest pytest-mock pytest-cov
pytest tests/                    # Run all tests
pytest tests/test_generator.py   # Run single test file
pytest tests/test_generator.py::test_upload -v  # Run single test
```

---

## Code Style Guidelines

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `kling_generator_falai.py` |
| Functions | snake_case | `get_model_short_name()` |
| Private methods | underscore prefix | `_process_queue()` |
| Classes | PascalCase | `FalAIKlingGenerator` |
| Dataclasses | PascalCase | `QueueItem` |
| Constants | UPPER_SNAKE_CASE | `VALID_EXTENSIONS` |
| Variables | snake_case | `image_path`, `output_folder` |
| Private attributes | underscore prefix | `self._progress_callback` |

### Formatting

- **Indentation:** 4 spaces (no tabs)
- **Strings:** Double quotes (`"string"` not `'string'`)
- **Line length:** ~120 characters (no strict enforcement)
- **No automated formatter** configured (Black, autopep8, etc.)

### Import Organization

```python
# 1. Standard library imports
import os
import json
import threading
from pathlib import Path
from typing import List, Optional, Callable

# 2. Third-party packages
import requests
from PIL import Image
from rich.console import Console

# 3. Local modules
from path_utils import get_config_path, VALID_EXTENSIONS
from kling_generator_falai import FalAIKlingGenerator

# Relative imports within kling_gui/ package
from .drop_zone import DropZone
from .video_looper import create_looped_video
```

### Type Hints

Always use type hints for function signatures:

```python
def get_output_video_path(
    image_path: str, 
    output_folder: str, 
    model_short: str = "kling", 
    prompt_slot: int = 1
) -> Path:
    """Get the default output video path for an image."""
    ...

def validate_file(self, file_path: str) -> tuple:
    """Returns (is_valid: bool, error_message: str)"""
    ...
```

Common type imports:
```python
from typing import List, Optional, Dict, Any, Callable, Tuple
```

### Docstrings

Use Google-style docstrings:

```python
def create_kling_generation(
    self,
    character_image_path: str,
    output_folder: str = None,
    custom_prompt: str = None,
    duration: int = 10
) -> Optional[str]:
    """Create Kling video via fal.ai.

    Args:
        character_image_path: Path to source image
        output_folder: Fallback output folder
        custom_prompt: Custom generation prompt
        duration: Video duration in seconds (default 10)

    Returns:
        Output video path on success, None on failure
    """
```

---

## Error Handling

### Pattern: Try-except at operation boundaries

```python
# API calls - use specific exceptions with retry logic
try:
    response = requests.post(url, headers=headers, json=payload, timeout=30)
except requests.exceptions.Timeout:
    logger.warning("Request timeout, retrying...")
    # Retry logic
except requests.exceptions.ConnectionError as e:
    logger.error(f"Connection error: {e}")
    return None
```

### Pattern: Per-item errors in batch processing

```python
# Continue processing remaining items on per-item errors
for item in items:
    try:
        result = process_item(item)
    except Exception as e:
        item.status = "failed"
        item.error_message = str(e)
        self.log(f"Error processing {item.filename}: {e}", "error")
        continue  # Don't abort entire batch
```

### Pattern: GUI error display

```python
# Log error, don't crash
try:
    result = risky_operation()
except Exception as e:
    self.log(f"Operation failed: {e}", "error")
    # GUI stays responsive
```

---

## Architecture Quick Reference

### Entry Points

| Entry | File | Description |
|-------|------|-------------|
| CLI | `kling_automation_ui.py` | Menu-driven terminal UI |
| GUI | `kling_gui/main_window.py` | Tkinter drag-and-drop interface |

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| Generator | `kling_generator_falai.py` | fal.ai API integration |
| Queue | `kling_gui/queue_manager.py` | Thread-safe processing queue |
| Config Panel | `kling_gui/config_panel.py` | Model/prompt/output settings |
| Drop Zone | `kling_gui/drop_zone.py` | Drag-and-drop + click-to-browse |
| Log Display | `kling_gui/log_display.py` | Color-coded scrolling log |
| Path Utils | `path_utils.py` | Path helpers, PyInstaller compat |

### Threading Model

```python
# GUI updates must use root.after() for thread safety
def update_from_worker_thread():
    self.root.after(0, lambda: self.update_display())

# Queue manager uses Lock for shared state
with self.lock:
    for item in self.items:
        if item.status == "pending":
            item.status = "processing"
            return item
```

---

## Key Implementation Patterns

### Progress Callback Pattern

```python
# Generator supports callback injection for verbose mode
def progress_callback(message: str, level: str = "info"):
    self.log_verbose(message, level)

if config.get("verbose_gui_mode", False):
    self.generator.set_progress_callback(progress_callback)
```

### Configuration Access

```python
# Config is JSON file, loaded at startup
config = self.load_config()  # Returns dict

# Access with defaults
use_source = config.get("use_source_folder", True)
model = config.get("current_model", "fal-ai/kling-video/v2.1/pro/image-to-video")

# Save after changes
self.save_config()
```

### Filename Generation

```python
# Output filename pattern: {image_stem}_kling_{model_short}_p{slot}.mp4
# Example: selfie_kling_k25turbo_p2.mp4

model_short = self.get_model_short_name()  # k25turbo, wan25, veo3, etc.
filename = f"{image_stem}_kling_{model_short}_p{prompt_slot}.mp4"
```

---

## Log Levels

| Level | Color | Usage |
|-------|-------|-------|
| info | Light gray | General information |
| success | Bright green | Completion messages |
| error | Coral red | Failures |
| warning | Yellow | Non-fatal issues |
| upload | Dark cyan | Upload progress (verbose) |
| task | Sky blue | Task creation (verbose) |
| progress | Gold | Generation progress (verbose) |
| debug | Gray | Debug info (verbose) |
| resize | Plum | Image resize (verbose) |
| download | Pale green | Download progress (verbose) |
| api | Orchid | API responses (verbose) |

---

## File Locations

| Purpose | Location |
|---------|----------|
| User config | `kling_config.json` (auto-generated) |
| GUI log | `kling_gui.log` |
| CLI log | `kling_automation.log` |
| Chrome profile | `chrome_profile/` (for balance tracker) |
| Distribution | `distribution/` (self-contained copy) |

---

## Valid Image Extensions

```python
VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tiff', '.tif'}
```

---

## Common Pitfalls

1. **Thread Safety:** Always use `threading.Lock()` when accessing shared queue state
2. **Tkinter Updates:** Never update UI from worker thread - use `root.after()`
3. **Path Handling:** Use `Path` objects, handle both Windows and Unix paths
4. **API Timeouts:** Always set timeout on requests (30s for API, 120s for downloads)
5. **Duplicate Detection:** Check both base and `_looped` variants when checking for existing videos
6. **Distribution Sync:** Files in `distribution/` must be manually synced with root

---

## Adding New Features

### New GUI Component

1. Create `kling_gui/new_component.py`
2. Add to `kling_gui/__init__.py` exports
3. Import and use in `kling_gui/main_window.py`

### New API Integration

1. Create new file in root (e.g., `new_api_client.py`)
2. Follow `FalAIKlingGenerator` pattern with progress callbacks
3. Import in queue_manager or create parallel processing path

### New CLI Command

1. Add method to `KlingAutomationUI` class in `kling_automation_ui.py`
2. Add menu option in `display_configuration_menu()`
3. Handle in `run_configuration_menu()` switch
