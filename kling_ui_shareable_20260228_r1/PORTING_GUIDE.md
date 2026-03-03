# Porting Guide: Simple ↔ Advanced Version

**Simple version:** `F:\claude\kling_ui_complete_2\kling_ui_shareable_20260228_r1`
**Advanced version:** `C:\claude\selfie-gen-ultimate\kling_ui_shareable_20260228_r1`

---

## File Categories

### 1. Identical — Copy As-Is

These files are (or should be) byte-identical between versions. When changing one, copy it straight to the other.

| File | Notes |
|------|-------|
| `models.json` | Shared model endpoint list + user_notes |
| `model_metadata.py` | Loads models.json, display name helpers |
| `model_schema_manager.py` | API schema fetching, caching, capabilities |
| `path_utils.py` | PyInstaller path resolution |
| `kling_gui/model_manager_dialog.py` | Model manager dialog (imports from `.theme`) |
| `kling_gui/queue_manager.py` | Queue logic, worker thread, model short names |
| `kling_gui/theme.py` | Shared colors/fonts (both versions have this file) |

### 2. Structural Differences — Manual Merge Required

#### `kling_gui/config_panel.py` (BIGGEST DIFFERENCE)

| Aspect | Simple | Advanced |
|--------|--------|----------|
| **COLORS** | `from .theme import COLORS, FONT_FAMILY` | **Inline `COLORS` dict + `FONT_FAMILY = "Segoe UI"`** (not imported) |
| **Health check** | Has `_start_endpoint_health_check()` + `_dead_endpoints` set | **No health check at all** |
| **Model combo width** | `width=42`, `expand=True` in grid | `width=36`, `padx=(5,10)`, no expand |
| **DnD imports** | None at top | Imports `tkinterdnd2` for mini drop zone |
| **Mini drop zone** | Not present | Has a small drag-and-drop zone inside config panel |
| **`_on_model_manager_saved()`** | Calls `_start_endpoint_health_check()` at end | Does NOT call health check |
| **`_load_config()` enrichment** | Calls `_start_api_enrichment()` after `_start_endpoint_health_check()` | Calls `_start_api_enrichment()` after model combo setup (no health check) |

**Porting strategy:** Apply functional changes (new methods, logic) to both, but preserve each version's structural skeleton. Never blindly overwrite.

#### `kling_gui/main_window.py`

| Aspect | Simple | Advanced |
|--------|--------|----------|
| **Layout** | Two-panel PanedWindow (left: config+dropzone, right: log+history) | **Notebook with 5+ tabs** (Video Gen, Selfie, Compare, etc.) |
| **Extra config keys** | `custom_models`, `hidden_models` | + `freeimage_api_key`, `bfl_api_key`, `selfie_selected_models`, carousel settings |
| **Theme** | `from .theme import COLORS, FONT_FAMILY` | Same import |

**Porting strategy:** Shared changes (config keys, defaults, sash position) are safe to apply. Layout/tab changes are version-specific — don't copy structure.

#### `kling_gui/drop_zone.py`

| Aspect | Simple | Advanced |
|--------|--------|----------|
| **COLORS** | `from .theme import COLORS, FONT_FAMILY` | **Inline `COLORS` dict** |
| **DnD** | Same TkinterDnD2 integration | Same |

**Porting strategy:** Functional changes port fine. Just watch the COLORS import.

#### `kling_gui/log_display.py`

| Aspect | Simple | Advanced |
|--------|--------|----------|
| **COLORS** | `from .theme import COLORS, FONT_FAMILY` | **Inline `COLORS` dict** |
| **Tags** | Same 11 color tags | Same |

**Porting strategy:** Same as drop_zone — functional changes port, watch COLORS.

#### `kling_generator_falai.py`

| Aspect | Simple | Advanced |
|--------|--------|----------|
| **freeimage key** | Uses only `falai_api_key` | Adds `freeimage_api_key` parameter for freeimage.host uploads |
| **Selfie mode** | Not present | Selfie-specific generation methods |

**Porting strategy:** Changes to video gen logic (API calls, parameters, schema validation) port cleanly. Selfie/freeimage additions are advanced-only.

### 3. Advanced-Only Files (Do Not Port to Simple)

These exist only in the advanced version:

| File | Purpose |
|------|---------|
| `fal_utils.py` | Shared fal.ai utility functions |
| `outpaint_generator.py` | Image outpainting via fal.ai |
| `selfie_generator.py` | Selfie generation pipeline |
| `selfie_prompt_composer.py` | Prompt templating for selfies |
| `vision_analyzer.py` | Image analysis via vision models |
| `kling_gui/carousel_widget.py` | Image carousel UI widget |
| `kling_gui/compare_panel.py` | Side-by-side comparison panel |
| `kling_gui/image_state.py` | Image state management |
| `kling_gui/tabs/` | Tab subpackage (video_tab, selfie_tab, etc.) |

### 4. Build Files

| File | Simple | Advanced |
|------|--------|----------|
| `kling_gui_direct.spec` | Base hidden imports + data | + extra hidden imports for advanced modules |
| `build_gui_exe.bat` | Version date only | Same — sync version date |

---

## Porting Checklist

When making changes that affect both versions:

1. **Start in the simple version** (cleaner, fewer moving parts)
2. **Copy identical files** from the table in Section 1 directly
3. **For config_panel.py**, apply changes surgically:
   - Copy new methods/functions as-is
   - Adjust COLORS references (import vs inline)
   - Skip health-check-related code in the advanced version
   - Preserve layout constants (width, padx, expand)
4. **For main_window.py**, only port shared config key changes
5. **For drop_zone.py / log_display.py**, port functional changes, keep COLORS source
6. **Test both versions** launch without errors after porting

---

## Common Pitfalls

- **Grep path confusion:** `C:\claude` and `F:\claude` are junctioned on this machine. Use explicit full paths when searching to avoid cross-contamination.
- **COLORS import:** The #1 source of porting bugs. Simple uses `from .theme import COLORS`, advanced has `COLORS = {...}` inline. If you copy a file that imports from theme into the advanced version, it will still work (theme.py exists in both), but the advanced version historically used inline dicts.
- **Health check references:** If you add code that touches `self._dead_endpoints` or calls `self._start_endpoint_health_check()`, it will crash in the advanced version where these don't exist.
- **Model combo layout:** Don't copy grid/pack layout lines between versions — the widget geometry differs.
