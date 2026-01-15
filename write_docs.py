#!/usr/bin/env python3
"""
Write documentation files to docs/ directory for Kling UI project.

Usage:
    python write_docs.py

This script creates:
    - docs/Structure.md (project file organization)
    - docs/Architecture.md (technical architecture)
"""

import sys
from pathlib import Path


def write_docs():
    """Write all documentation files."""

    # Ensure docs directory exists
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    # Define all files as a dictionary
    docs_content = {
        "Structure.md": """# Project Structure

## File Layout

```text
kling_ui_complete_2/
├── AGENTS.md                  # Guide for AI agents working on this codebase
├── CLAUDE.md                  # Claude Code configuration and rules
├── README.txt                 # Basic user instructions
├── requirements.txt           # Python dependencies
├── kling_config.json          # User configuration (generated)
├── kling_history.json         # Job history (generated)
│
├── kling_automation_ui.py     # CLI Entry Point
├── kling_generator_falai.py   # Core Logic: fal.ai API integration
├── path_utils.py              # Helper functions for file paths (PyInstaller safe)
├── dependency_checker.py      # Script to verify installed packages
├── balance_tracker.py         # Selenium-based balance checker logic
├── selenium_balance_checker.py# Entry point for balance checking
├── write_docs.py              # Documentation generation script
│
├── kling_gui/                 # GUI Package
│   ├── __init__.py            # Exports GUI components
│   ├── main_window.py         # Main GUI controller and window
│   ├── queue_manager.py       # Thread-safe job queue
│   ├── drop_zone.py           # Drag-and-drop widget
│   ├── config_panel.py        # Settings UI
│   ├── log_display.py         # Scrolling log widget
│   └── video_looper.py        # Video post-processing (looping)
│
├── docs/                      # Documentation
│   ├── Architecture.md        # System architecture and data flow
│   └── Structure.md           # This file map
│
└── distribution/              # Self-contained build artifacts (for release)
```

## Key File Descriptions

*   **`kling_automation_ui.py`**: The command-line interface. Use this for batch processing folders of images without a GUI.
*   **`kling_gui/main_window.py`**: The graphical interface. Provides a visual queue, drag-and-drop, and real-time logs.
*   **`kling_generator_falai.py`**: The "engine" of the application. It handles authentication, uploading to file hosts, and communicating with the fal.ai API.
*   **`queue_manager.py`**: Bridges the GUI and the Generator. It ensures long-running API calls don't freeze the interface.
""",
        "Architecture.md": """# Kling UI Architecture

## Overview
This document describes the high-level architecture of the Kling UI automation tool, including its data flow, component interactions, and key classes.

## System Components

### 1. Entry Points
The application has two primary entry points:
*   **CLI (`kling_automation_ui.py`)**: A terminal-based menu system for configuring settings and running batch jobs.
*   **GUI (`kling_gui/main_window.py`)**: A Tkinter-based graphical interface with drag-and-drop support, real-time queue management, and visual feedback.

### 2. Core Logic (`kling_generator_falai.py`)
The `FalAIKlingGenerator` class encapsulates all interactions with the `fal.ai` API.
*   **Responsibilities**:
    *   Image uploading (to `freeimage.host`).
    *   API request construction (payloads for different models).
    *   Job submission and status polling.
    *   Video downloading and saving.
    *   Duplicate detection.
    *   Concurrent batch processing.

### 3. GUI Architecture (`kling_gui/`)
The GUI is built using Python's `tkinter` and follows a modular design.

*   **`main_window.py`**: The root controller. It initializes the generator, queue manager, and UI components. It handles the main event loop and window lifecycle.
*   **`queue_manager.py`**: Manages the processing queue in a separate thread to keep the UI responsive.
    *   Uses `threading.Lock` for thread-safe access to the queue.
    *   communicates with the generator to process items.
    *   Updates the UI via callbacks scheduled with `root.after()`.
*   **`drop_zone.py`**: Handles drag-and-drop events (using `tkinterdnd2`) and file selection.
*   **`config_panel.py`**: A dedicated panel for user settings (model selection, prompt slots, duration, etc.).
*   **`log_display.py`**: A scrolling text widget for displaying color-coded logs.

### 4. Data Flow

#### GUI Job Submission
1.  User drags images to the **Drop Zone**.
2.  `DropZone` triggers a callback in `MainWindow`.
3.  `MainWindow` calls `QueueManager.add_to_queue()`.
4.  `QueueManager` adds the item to its internal list (status: "pending").
5.  The background worker thread in `QueueManager` picks up the pending item.
6.  `QueueManager` calls `FalAIKlingGenerator.create_kling_generation()`.
7.  **Generator**:
    *   Uploads image.
    *   Sends request to `fal.ai`.
    *   Polls for completion.
    *   Downloads video.
8.  `QueueManager` updates item status (success/fail) and triggers a UI update callback.

#### CLI Batch Processing
1.  User selects "Process Folder" in the CLI menu.
2.  `KlingAutomationUI` gathers configuration.
3.  `KlingAutomationUI` calls `FalAIKlingGenerator.process_all_images_concurrent()`.
4.  **Generator**:
    *   Scans the directory.
    *   Uses `ThreadPoolExecutor` to process multiple images in parallel.
    *   Logs progress to the console.

## Configuration Persistence
*   **File**: `kling_config.json`
*   **Mechanism**: A simple JSON object storing key-value pairs.
*   **Loading**: Loaded at startup by `MainWindow` (GUI) or `KlingAutomationUI` (CLI).
*   **Saving**: Saved automatically when settings change in the GUI or when explicitly saved in the CLI.
""",
    }

    # Write all files
    written_files = []
    for filename, content in docs_content.items():
        filepath = docs_dir / filename
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            written_files.append((filename, len(content)))
            print(f"✓ Written {filename} ({len(content):,} bytes)")
        except Exception as e:
            print(f"✗ Failed to write {filename}: {e}", file=sys.stderr)
            return False

    print(f"\\n✓ All {len(written_files)} documentation files created successfully!")
    return True


if __name__ == "__main__":
    success = write_docs()
    sys.exit(0 if success else 1)
