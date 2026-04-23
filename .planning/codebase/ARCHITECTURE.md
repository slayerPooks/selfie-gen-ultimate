# Architecture

**Analysis Date:** 2026-01-14

## Pattern Overview

**Overall:** Dual-Mode Desktop Application (CLI + GUI) with Shared Services

**Key Characteristics:**
- Dual entry points (CLI menu system and Tkinter GUI)
- Shared core generator service (`kling_generator_falai.py`)
- Callback-based progress reporting
- Thread-safe queue processing in GUI mode
- File-based configuration persistence

## Layers

**Presentation Layer (CLI):**
- Purpose: Terminal-based menu interface
- Contains: Rich console panels, input prompts, progress display
- Location: `kling_automation_ui.py`
- Depends on: Generator service, configuration
- Used by: Direct user invocation

**Presentation Layer (GUI):**
- Purpose: Visual interface with drag-and-drop
- Contains: Tkinter widgets, event handlers
- Location: `kling_gui/main_window.py`, `kling_gui/config_panel.py`, `kling_gui/drop_zone.py`, `kling_gui/log_display.py`
- Depends on: Queue manager, generator service
- Used by: GUI launcher

**Queue Management Layer:**
- Purpose: Thread-safe processing queue with worker thread
- Contains: `QueueManager`, `QueueItem` dataclass
- Location: `kling_gui/queue_manager.py`
- Depends on: Generator service
- Used by: GUI main window

**Service Layer:**
- Purpose: Core business logic for video generation
- Contains: API calls, image processing, polling logic
- Location: `kling_generator_falai.py`
- Depends on: External APIs (fal.ai, freeimage.host)
- Used by: Both CLI and GUI layers

**Utility Layer:**
- Purpose: Shared helpers and path management
- Contains: Path resolution, file extension validation
- Location: `path_utils.py`, `dependency_checker.py`
- Depends on: Python standard library only
- Used by: All layers

**Optional Services:**
- Balance Tracker: `selenium_balance_checker.py`, `balance_tracker.py`
- Video Looper: `kling_gui/video_looper.py`

## Data Flow

**Image-to-Video Generation:**

1. User provides image (file browser, drag-drop, or folder batch)
2. Image validated for supported format (`path_utils.py`)
3. Image resized/converted if needed (`kling_generator_falai.py:_resize_image_if_needed`)
4. Image uploaded to freeimage.host for public URL
5. Generation job submitted to fal.ai queue API
6. Status URL polled with exponential backoff (5s → 10s → 15s)
7. Video downloaded on completion
8. Optional: FFmpeg creates looped version

**State Management:**
- File-based: All settings persist in `kling_config.json`
- In-memory: Queue state, processing progress
- Each CLI command execution is independent
- GUI maintains state during session

## Key Abstractions

**FalAIKlingGenerator:**
- Purpose: Encapsulate all fal.ai API interactions
- Location: `kling_generator_falai.py`
- Pattern: Class with progress callback injection
- Methods: `generate_video()`, `_upload_image()`, `_poll_status()`

**QueueManager:**
- Purpose: Thread-safe processing queue
- Location: `kling_gui/queue_manager.py`
- Pattern: Worker thread with Lock-protected queue
- Methods: `add_items()`, `start_processing()`, `_process_queue()`

**QueueItem:**
- Purpose: Data structure for queue entries
- Location: `kling_gui/queue_manager.py`
- Pattern: Python dataclass with status tracking

**ConfigPanel:**
- Purpose: Model/output/prompt settings widget
- Location: `kling_gui/config_panel.py`
- Pattern: Tkinter Frame with callbacks

## Entry Points

**CLI Entry:**
- Location: `kling_automation_ui.py`
- Triggers: `python kling_automation_ui.py`
- Responsibilities: Display menu, route to commands, manage config

**GUI Entry:**
- Location: `kling_gui/main_window.py` (class), invoked from CLI option 6
- Triggers: Menu option or `python -c "from kling_gui import KlingGUIWindow; KlingGUIWindow().run()"`
- Responsibilities: Initialize Tkinter, assemble components, handle events

## Error Handling

**Strategy:** Try-except blocks at operation boundaries, logging, user feedback

**Patterns:**
- Generator: Retry logic with exponential backoff for API calls
- GUI: Try-except wrapping file operations, logging errors
- Queue: Per-item error capture, continues processing remaining items

## Cross-Cutting Concerns

**Logging:**
- CLI: Rich console output with colored panels
- GUI: Color-coded LogDisplay widget + file logging (`kling_debug.log`)
- Levels: info, success, error, warning, upload, task, progress, debug

**Configuration:**
- JSON file (`kling_config.json`) loaded at startup
- Auto-saved after user changes
- Schema documented in `CLAUDE.md`

**Threading:**
- GUI: Daemon worker thread for queue processing
- Balance tracker: Background daemon thread
- Thread safety: `threading.Lock()` for shared state
- GUI updates: `root.after()` for thread-safe Tkinter calls

---

*Architecture analysis: 2026-01-14*
*Update when major patterns change*
