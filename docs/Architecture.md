# Kling UI Architecture

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
