# Codebase Structure

**Analysis Date:** 2026-01-14

## Directory Layout

```
kling_ui_complete_2/
├── kling_gui/                  # GUI package (Tkinter components)
│   ├── __init__.py            # Package exports
│   ├── main_window.py         # Main GUI window assembly
│   ├── config_panel.py        # Model/output/prompt settings
│   ├── queue_manager.py       # Thread-safe processing queue
│   ├── drop_zone.py           # Drag-and-drop widget
│   ├── log_display.py         # Color-coded log widget
│   └── video_looper.py        # FFmpeg ping-pong loop
├── distribution/               # Self-contained distribution folder
│   ├── kling_gui/             # Duplicate GUI package
│   ├── hooks/                 # PyInstaller hooks
│   ├── run_kling_ui.bat       # Auto-venv setup launcher
│   ├── kling_automation_ui.py # Duplicate CLI
│   └── ...                    # Other duplicated files
├── kling_automation_ui.py      # CLI menu system (main entry)
├── kling_generator_falai.py    # fal.ai API integration
├── selenium_balance_checker.py # Chrome automation for balance
├── balance_tracker.py          # Background balance tracker
├── dependency_checker.py       # Package/tool checker
├── path_utils.py               # Path helpers and validation
├── kling_config.json           # User configuration (generated)
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # Project documentation
└── README.md                   # User guide
```

## Directory Purposes

**kling_gui/**
- Purpose: Tkinter GUI components
- Contains: Python modules for each UI component
- Key files: `main_window.py` (assembles UI), `queue_manager.py` (processing)
- Subdirectories: None

**distribution/**
- Purpose: Self-contained distribution for end users
- Contains: Complete copy of all source files + launcher
- Key files: `run_kling_ui.bat` (auto-venv setup)
- Subdirectories: `kling_gui/` (duplicate), `hooks/` (PyInstaller)

## Key File Locations

**Entry Points:**
- `kling_automation_ui.py` - CLI menu system (primary entry)
- `kling_gui/main_window.py` - GUI window class (`KlingGUIWindow`)

**Configuration:**
- `kling_config.json` - User settings (auto-generated)
- `requirements.txt` - Python dependencies
- `CLAUDE.md` - Project documentation for AI assistants

**Core Logic:**
- `kling_generator_falai.py` - fal.ai API calls, image processing
- `kling_gui/queue_manager.py` - Thread-safe queue, worker thread

**Optional Features:**
- `selenium_balance_checker.py` - Chrome automation
- `balance_tracker.py` - Background balance monitoring
- `kling_gui/video_looper.py` - FFmpeg video looping

**Utilities:**
- `path_utils.py` - Path resolution, extension validation
- `dependency_checker.py` - Package/tool availability check

## Naming Conventions

**Files:**
- snake_case for all Python files: `kling_generator_falai.py`
- Underscore prefix for internal modules: None used
- Test files: None present (no `test_*.py`)

**Directories:**
- snake_case for directories: `kling_gui/`
- Lowercase for special directories: `distribution/`

**Special Patterns:**
- `__init__.py` for package exports
- `CLAUDE.md` uppercase for project docs
- `_kling_{model}_p{N}.mp4` output naming pattern

## Where to Add New Code

**New GUI Component:**
- Implementation: `kling_gui/{component_name}.py`
- Export: Add to `kling_gui/__init__.py`
- Usage: Import in `kling_gui/main_window.py`

**New API Integration:**
- Implementation: New file in root (e.g., `new_api_client.py`)
- Usage: Import in `kling_generator_falai.py` or create parallel generator

**New CLI Command:**
- Implementation: Add method to `KlingAutomationUI` class in `kling_automation_ui.py`
- Menu: Add to `main_menu()` method

**Utilities:**
- Shared helpers: `path_utils.py`
- New utility file: Root directory

## Special Directories

**distribution/**
- Purpose: Self-contained copy for end users without dev environment
- Source: Manual duplication from root (not auto-generated)
- Committed: Yes (included in repo)
- Issue: Must be manually synced with root changes

**chrome_profile/** (auto-generated)
- Purpose: Persistent Chrome session for balance tracker
- Source: Created by Selenium on first login
- Committed: No (gitignored)

---

*Structure analysis: 2026-01-14*
*Update when directory structure changes*
