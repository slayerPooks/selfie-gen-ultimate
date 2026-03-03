# Session Handoff: Redirect All Generated Output to `gen-images/` Subfolder
Created: 2026-03-03

---

## Goal
Redirect all generated output (selfies, outpaints, face crops, polished crops, videos) into a `gen-images/` subfolder within the source image's directory, instead of saving directly next to the source image. Also fix the face crop `%TEMP%` bug where EXIF correction overwrites `self._source_path` to a temp path.

## Goal Clarifications
- Custom output folder mode remains unchanged — only the "save next to source" / fallback paths redirect to `gen-images/`
- Session persistence (just implemented) serializes absolute paths — `gen-images/` paths work without changes
- Polish output inherits the correct directory automatically from `_save_crop()`'s return path

## User Emphasis (IMPORTANT)
> The user provided a detailed 5-step plan and asked for exact implementation.
- The plan was approved in plan mode before implementation began
- No deviations from the plan were requested

## Current State
- **Status:** Implementation complete, NOT committed, NOT tested
- **What's done:**
  - Step 1: `get_gen_images_folder()` helper added to `path_utils.py`
  - Step 2: Selfie tab `_resolve_output_folder()` source branch redirects to `gen-images/`
  - Step 3: Outpaint tab fallback branch redirects to `gen-images/`
  - Step 4: Face crop tab — `_original_path` field added, `_save_crop()` rewritten with `gen-images/` + collision guard
  - Step 5: Video queue — source-folder branch uses `gen-images/`, passes `use_source_folder=False` to generator
- **What's pending:**
  - Manual GUI testing (no automated tests exist)
  - Git commit
- **Active file(s):** All changes are unstaged working tree modifications

## Key Decisions
- `get_gen_images_folder()` is pure path computation (no `os.makedirs`) — callers create the dir
- Face crop collision guard uses `_crop_2.jpg`, `_crop_3.jpg` pattern (not timestamps)
- Queue manager passes `use_source_folder=False` to the generator to prevent it from recomputing path back to source dir
- Fallback exception handler in `_save_crop()` still falls back to `tempfile.gettempdir()` if `gen-images/` write fails

## Files Modified (this session)
- `path_utils.py` — Added `get_gen_images_folder(source_path)` returning `{source_dir}/gen-images`
- `kling_gui/tabs/selfie_tab.py` — Import + `_resolve_output_folder()` source branch uses `gen-images/`
- `kling_gui/tabs/outpaint_tab.py` — Import + fallback branch uses `gen-images/` + `os.makedirs()`
- `kling_gui/tabs/face_crop_tab.py` — Import + `_original_path` field + rewritten `_save_crop()` with collision guard
- `kling_gui/queue_manager.py` — Import + both source-folder/fallback branches use `gen-images/` + `use_source_folder=False` in `_generate_video` call

## Files NOT Modified (per plan)
- `selfie_generator.py` — Takes `output_folder` param, works with any path
- `outpaint_generator.py` — Same pattern
- `kling_generator_falai.py` — Its `use_source_folder=True` branch bypassed by queue_manager change
- `image_state.py` / `session_manager.py` — Absolute paths serialize fine

## Active PRs
- No PRs created yet. Branch: `feat/schema-driven-config`

## DO NOTs & Constraints
- **DO NOT** modify `selfie_generator.py` or `outpaint_generator.py` — they already accept `output_folder` as parameter
- **DO NOT** change `kling_generator_falai.py` — the `use_source_folder=False` trick in queue_manager handles it
- **DO NOT** forget that many other files are also modified on this branch (17 total) from prior work — the gen-images changes are only 5 of them
- Pyright "could not be resolved" warnings are pre-existing (runtime imports depend on `sys.path` at execution time, not static analysis)

## Relevant Artifacts

Key helper function added to `path_utils.py`:
```python
def get_gen_images_folder(source_path: str) -> str:
    source_dir = os.path.dirname(os.path.abspath(source_path))
    return os.path.join(source_dir, "gen-images")
```

Face crop `_save_crop()` collision pattern:
```python
out_path = gen_dir / f"{origin.stem}_crop.jpg"
counter = 2
while out_path.exists():
    out_path = gen_dir / f"{origin.stem}_crop_{counter}.jpg"
    counter += 1
```

## Verification Checklist (from plan)
1. **Selfie**: Load image, "save next to source", generate with 2+ models → outputs in `gen-images/`
2. **Face crop**: Load photo, detect, "Send to Selfie" → `_crop.jpg` in `gen-images/`, not `%TEMP%`. Repeat → `_crop_2.jpg`
3. **Polish**: After face crop, "Polish Crop" → `_crop_polished_1.png` in `gen-images/` (same dir as crop)
4. **Outpaint**: Outpaint without custom folder → result in `gen-images/`
5. **Video**: Add images, "use source folder", process → videos in `gen-images/`
6. **Session persistence**: Generate, save session, reopen, load → `gen-images/` paths restore in carousel

## Next Action
1. Launch the GUI (`python kling_automation_ui.py` → option 6, or run directly) and manually test each verification step above
2. Once verified, commit all changes with a descriptive message
3. Consider adding `gen-images/` to `.gitignore` if it isn't already

---

## Resume Instructions

To continue this work in a fresh session:

```text
Read handoffs/2026-03-03_gen-images-redirect.md and resume the work.

CRITICAL:
- Check "User Emphasis (IMPORTANT)" first - these are things I had to repeat.
- Check "DO NOTs & Constraints" to avoid regressions.
- Start with "Next Action" — manual GUI testing, then commit.
- Branch is feat/schema-driven-config with 17 modified files total (only 5 are from this task).
```
