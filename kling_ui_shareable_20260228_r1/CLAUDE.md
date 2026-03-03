# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kling UI is an AI media generation tool using fal.ai APIs. It provides a 4-tab Tkinter GUI for portrait analysis, selfie generation, image outpainting, and batch video generation, plus a CLI mode via Rich.

## Commands

```bash
# Setup
python -m venv venv && venv/Scripts/pip install -r requirements.txt

# Run CLI (menu-driven)
python kling_automation_ui.py

# Launch GUI directly
python -c "from kling_gui import KlingGUIWindow; KlingGUIWindow().run()"

# Check/install dependencies
python dependency_checker.py

# Build standalone EXE (PyInstaller)
build_gui_exe.bat
```

There are no tests. Verify changes by running the GUI and testing the relevant tab.

## Architecture

### Entry Points

- `kling_automation_ui.py` — CLI menu system (77K lines, Rich UI). Option 6 launches GUI.
- `kling_gui/main_window.py` — GUI entry point. Creates the 4-tab `ttk.Notebook`.
- `gui_launcher.py` — PyInstaller-compatible GUI bootstrap.
- `run_kling_ui.bat` / `run_gui.bat` / `start_gui.bat` — Windows launchers with auto-venv.

### GUI Tab Architecture (`kling_gui/tabs/`)

The GUI uses a tabbed layout with shared state:

| Tab | File | Class | Purpose |
|-----|------|-------|---------|
| 1. Prep | `prep_tab.py` | `PrepTab` | Vision AI analysis of portraits (OpenRouter API) |
| 2. Selfie | `selfie_tab.py` | `SelfieTab` | Generate selfies from identity reference via fal.ai |
| 3. Outpaint | `outpaint_tab.py` | `OutpaintTab` | Expand images using fal.ai outpaint |
| 4. Video | `video_tab.py` | `VideoTab` | Batch video generation (wraps ConfigPanel + DropZone + Queue) |

All tabs share an `ImageSession` instance for image pipeline state and a `log_callback` for the unified `LogDisplay`.

### Image Pipeline State (`kling_gui/image_state.py`)

`ImageSession` tracks images through the multi-tab pipeline. Each `ImageEntry` has a `source_type` ("input", "selfie", "outpaint") and flows through:

```
Input image → Prep (analyze) → Selfie (generate) → Outpaint (expand) → Video (animate)
```

The `ImageCarousel` widget (`carousel_widget.py`) provides visual navigation across all pipeline stages.

### Shared GUI Components (`kling_gui/`)

| Module | Purpose |
|--------|---------|
| `theme.py` | `COLORS` dict and `FONT_FAMILY` — single source of truth for all styling |
| `config_panel.py` | Model/output/prompt settings for the Video tab |
| `drop_zone.py` | Drag-and-drop + click-to-browse widget (requires `tkinterdnd2`) |
| `queue_manager.py` | Thread-safe processing queue with `QueueItem` dataclass |
| `log_display.py` | Color-coded scrolling log with verbose mode levels |
| `video_looper.py` | FFmpeg ping-pong loop via `create_looped_video()` |

### Backend Generators

| Module | Class | External API |
|--------|-------|-------------|
| `kling_generator_falai.py` | `FalAIKlingGenerator` | fal.ai queue API (video gen) |
| `selfie_generator.py` | `SelfieGenerator` | fal.ai (FLUX PuLID, Nano Banana, SeDream, etc.) |
| `outpaint_generator.py` | `OutpaintGenerator` | fal.ai outpaint |
| `vision_analyzer.py` | `VisionAnalyzer` | OpenRouter chat completions (vision) |
| `selfie_prompt_composer.py` | `SelfiePromptComposer` | None (local prompt assembly) |

All generators follow the same pattern: `set_progress_callback(cb)` for GUI logging, `_report(msg, level)` internally.

### Shared Utilities

| Module | Purpose |
|--------|---------|
| `fal_utils.py` | `upload_to_freeimage()`, `fal_queue_submit()`, `fal_queue_poll()`, `fal_download_file()` — shared by all fal.ai generators |
| `model_metadata.py` | Loads `MODEL_METADATA` from `models.json`, provides `get_model_by_endpoint()` lookups |
| `model_schema_manager.py` | Queries and caches fal.ai model parameter schemas (TTL-based) |
| `path_utils.py` | PyInstaller-compatible path resolution (`get_app_dir()`, `get_config_path()`, `is_frozen()`) |

### Data-Driven Model Configuration

Video models are defined in `models.json` (not hardcoded). Each entry has: `name`, `endpoint`, `release`, `est_cost_10s`, `duration_options`, `duration_default`, `notes`. `model_metadata.py` loads this at import time with a hardcoded fallback list.

Selfie models are hardcoded in `SelfieGenerator.AVAILABLE_MODELS` as a list of dicts with `endpoint`, `label`, `slug`, `api_url`.

### API Keys Required

| Key | Config Field | Used By |
|-----|-------------|---------|
| fal.ai | `falai_api_key` | All generators (video, selfie, outpaint) |
| Freeimage.host | `freeimage_api_key` | Image uploads (fal.ai requires public URLs) |
| OpenRouter | `openrouter_api_key` | Vision analysis in Prep tab |

### Configuration (`kling_config.json`)

Auto-generated, persisted JSON. Key sections:
- Video: `saved_prompts` (6 slots), `negative_prompts`, `current_model`, `video_duration`, `loop_videos`
- Selfie: `selfie_selected_models` (checkbox state), `selfie_prompt_template`, `selfie_scene_templates`, `selfie_output_mode`, `selfie_id_weight`, `selfie_width/height`
- Outpaint: `outpaint_expand_*` (L/R/T/B pixels), `outpaint_prompt`, `outpaint_format`
- Vision: `openrouter_api_key`, `openrouter_model`, `openrouter_vision_system_prompt`
- UI state: `window_geometry`, `sash_*` positions

Defaults for new installs come from `default_config_template.json`.

### Key Data Flows

**Video generation:**
```
Image → freeimage.host upload → fal.ai queue submit → poll status_url → download .mp4
```
Output naming: `{imagename}_kling_{model_short}_{pN}.mp4`

**Selfie generation:**
```
Portrait → VisionAnalyzer (OpenRouter) → JSON handoff → SelfiePromptComposer template → fal.ai identity model → result image
```
The vision analyzer returns structured JSON (`hair`, `skin`, `eyes`, `face_shape`, `age_range`, `gender`, `clothing`, `expression`) which fills the prompt template. FLUX PuLID gets an extra realism suffix appended. DeepFace computes face similarity scores.

**Outpaint:**
```
Image → freeimage.host upload → fal.ai outpaint endpoint → download expanded image
```

### Threading Model

- GUI updates via `root.after()` for thread-safe Tkinter calls
- `QueueManager` uses `threading.Lock()` on its items list, daemon worker thread
- All generators run in background threads spawned by their respective tabs
- Balance tracker (optional) runs headless Chrome in a daemon thread

### Build / Distribution

- `build_gui_exe.bat` runs PyInstaller with `kling_gui_direct.spec`
- `hooks/hook-tkinterdnd2.py` — custom PyInstaller hook for tkinterdnd2
- `path_utils.py` ensures correct paths whether running as script or frozen exe
- `create_icon.py` generates `kling_ui.ico` from scratch
