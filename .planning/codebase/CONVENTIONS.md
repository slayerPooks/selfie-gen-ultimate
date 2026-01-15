# Coding Conventions

**Analysis Date:** 2026-01-14

## Naming Patterns

**Files:**
- snake_case for all Python files: `kling_generator_falai.py`, `queue_manager.py`
- No prefix conventions for internal/private modules
- Test files: Not present (no `test_*.py` convention established)

**Functions:**
- snake_case for all functions: `get_model_short_name()`, `start_processing()`
- Private methods with single underscore: `_process_queue()`, `_report_progress()`
- No special prefix for async functions (none used; threading instead)

**Variables:**
- snake_case for variables: `image_path`, `output_folder`, `custom_prompt`
- Instance attributes: snake_case, no prefix
- Private attributes: Single underscore prefix: `self._progress_callback`

**Types:**
- PascalCase for classes: `FalAIKlingGenerator`, `QueueManager`, `ConfigPanel`
- PascalCase for dataclasses: `QueueItem`
- No interface naming convention (Python duck typing)

**Constants:**
- UPPER_SNAKE_CASE for module-level constants
- Examples: `COLORS`, `VALID_EXTENSIONS`, `MAX_QUEUE_SIZE`, `FALLBACK_MODELS`
- Location: Top of module files

## Code Style

**Formatting:**
- 4-space indentation consistently
- Double quotes for strings (`"string"` not `'string'`)
- No enforced line length (no config found), ~120 chars typical
- No automated formatter configured

**Linting:**
- None configured
- No `.flake8`, `pyproject.toml`, or linting config files
- Manual code review only

## Import Organization

**Order:**
1. Standard library imports (`import os`, `import json`)
2. Third-party packages (`import requests`, `from PIL import Image`)
3. Local modules (`from path_utils import ...`, `from .drop_zone import ...`)

**Grouping:**
- Blank line between groups
- No alphabetical sorting enforced

**Path Aliases:**
- Relative imports within `kling_gui/` package: `from .drop_zone import DropZone`
- Absolute imports for root-level modules

## Error Handling

**Patterns:**
- Try-except blocks at operation boundaries
- Specific exceptions where predictable: `except requests.RequestException`
- Broad `except Exception` for unexpected errors with logging
- Retry logic with exponential backoff for API calls

**Error Types:**
- Log error before propagating
- Continue processing remaining items on per-item errors
- GUI: Display error in log widget, don't crash

**Logging:**
- Callback pattern for progress/error reporting
- CLI: Rich console output
- GUI: LogDisplay widget + file logging

## Logging

**Framework:**
- Python `logging` module (`kling_gui/main_window.py`)
- Rich console for CLI (`kling_automation_ui.py`)
- Custom callback pattern for GUI verbose mode

**Levels:**
- info, success, error, warning (standard)
- upload, task, progress, debug, resize, download, api (verbose mode)

**Patterns:**
- Callback injection: `generator.set_progress_callback(callback)`
- Color-coded output in GUI (`kling_gui/log_display.py`)

## Comments

**When to Comment:**
- Complex regex patterns: `kling_gui/config_panel.py:50-53`
- Non-obvious business logic
- Configuration schema documentation

**Docstrings:**
- Google-style with Args and Returns sections
- Present in most public methods
- Module docstrings: Single-line description at top

**Example:**
```python
def get_output_video_path(image_path: str, output_folder: str, model_short: str = "kling", prompt_slot: int = 1) -> Path:
    """Get the default output video path for an image.

    Args:
        image_path: Path to the source image
        output_folder: Folder where video will be saved
        model_short: Short model identifier (e.g., 'k25turbo', 'wan25')
        prompt_slot: Current prompt slot (1, 2, or 3)
    """
```

**TODO Comments:**
- Format: `# TODO: description`
- No username or issue tracking convention

## Function Design

**Size:**
- No enforced limit
- Some large functions exist (should be refactored)

**Parameters:**
- Type hints consistently used
- Default values for optional parameters
- `Optional[Type]` for nullable parameters

**Return Values:**
- Type hints on returns: `-> str`, `-> Path`, `-> Optional[dict]`
- `None` returned for error cases in some methods

## Module Design

**Exports:**
- Explicit `__all__` in `kling_gui/__init__.py`
- Named imports preferred

**Package Structure:**
- `kling_gui/` as only package
- Root-level modules for core functionality

**Type Hints:**
- Consistently used across codebase
- `Callable`, `Optional`, `List`, `Dict` from typing module

---

*Convention analysis: 2026-01-14*
*Update when patterns change*
