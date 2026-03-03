# Session Handoff: B6 + B7 Concurrency Bug Fixes in kling_generator_falai.py
Created: 2026-03-02 09:35

---

## Goal
Fix two MEDIUM-priority concurrency bugs (B6 and B7) in `kling_generator_falai.py` in the DEST repo (`C:\claude\selfie-gen-ultimate\kling_ui_shareable_20260228_r1`). These are the last two items from a larger audit pass. The plan is fully written and approved — just needs clean implementation.

## Goal Clarifications
- This session did a MASSIVE amount of prior work (porting video gen fixes from SOURCE to DEST, EXIF fix, face_crop_tab button routing, Pyright cleanup, full 60-item audit). The B6+B7 plan was the LAST thing written before context ran out.
- The plan file at `C:\Users\d0nbxx\.claude\plans\spicy-snuggling-cocke.md` contains the **approved, detailed plan** for B6+B7. Read it first.
- The user said implementation was "kicked off but has issues" — meaning a previous attempt at implementing the plan may have left partial/broken changes in the file. **Check the current state of `kling_generator_falai.py` carefully before making edits.**

## User Emphasis (IMPORTANT)
> These are things the user repeated multiple times or stressed as critical.
- **"Do NOT touch UI files, `models.json`, `queue_manager.py`, or anything else"** — only `kling_generator_falai.py`
- **"Keep the diffs as small and surgical as possible so we don't break the working pipeline"**
- **"Do NOT touch the theme, the UX, or any working logic"**
- The user values minimal, targeted changes. Don't over-engineer.

## Current State
- **Status:** Plan approved, implementation may be partially started (with issues)
- **What's done (prior sessions):**
  - Full video generation port from SOURCE to DEST (7 bugs across 8 files)
  - EXIF rotation fix in `face_crop_tab.py`
  - Two-button routing (Phase 1/Phase 2) in face_crop_tab + main_window
  - Pyright cleanup + `pyrightconfig.json`
  - Full 60-item codebase audit (HIGH/MEDIUM/LOW)
  - HIGH-priority fixes were planned but NOT all implemented in code yet
- **What's pending:** B6 + B7 fixes in `kling_generator_falai.py`
- **Active file:** `C:\claude\selfie-gen-ultimate\kling_ui_shareable_20260228_r1\kling_generator_falai.py`

## Key Decisions
- **B6 fix uses lock + reservation set (not just a lock):** A lock alone doesn't prevent TOCTOU because the file isn't written to disk between lock release and next thread's scan. The reservation set tracks allocated-but-not-yet-written filenames.
- **B7 fix uses snapshot-then-release pattern:** Counters are read under lock, callback is called outside lock. This prevents worker thread serialization on UI latency.
- **Scope is exactly 1 file:** `kling_generator_falai.py` only.

## Files Modified (this session, in DEST repo)

Previously modified files (from earlier work in this same long session):
- `models.json` — full replacement with 13-model list
- `default_config_template.json` — endpoint fix
- `model_metadata.py` — added `get_prompt_limit()` + fallback fix
- `model_schema_manager.py` — safety check + health check functions
- `kling_generator_falai.py` — 10+ surgical video gen fixes (EXIF, duration, URLs, etc.)
- `kling_gui/queue_manager.py` — `_model_short_from_endpoint()` updated
- `kling_gui/main_window.py` — `_migrate_endpoints()` + two-button notebook switcher
- `kling_gui/tabs/face_crop_tab.py` — EXIF fix + two-button routing + Pyright narrowing
- `pyrightconfig.json` — NEW (Pyright noise suppression)

**Still TODO (the B6+B7 plan):**
- `kling_generator_falai.py` — concurrency fixes

## DO NOTs & Constraints
- **DO NOT** touch any UI files (`main_window.py`, `config_panel.py`, `drop_zone.py`, `log_display.py`, tabs)
- **DO NOT** touch `models.json`, `queue_manager.py`, `model_schema_manager.py`, `fal_utils.py`
- **DO NOT** modify working video generation logic (submit, poll, download, URL extraction)
- **DO NOT** change method signatures or public API of `FalAIKlingGenerator`
- The implementation may have been partially attempted — **read the current file state before editing**

## The Plan (Summary)

Full plan is at: `C:\Users\d0nbxx\.claude\plans\spicy-snuggling-cocke.md`

### B6 — TOCTOU Race in `get_output_filename()`
1. Add `self._filename_lock = threading.Lock()` and `self._reserved_filenames: set = set()` in `__init__`
2. Wrap `get_output_filename()` scan+allocate in `self._filename_lock`, also check reservation set
3. Add `self._reserved_filenames.discard(filename)` after file write + in error paths

### B7 — Progress Callback Under Lock in `process_all_images_concurrent()`
3 occurrences where `progress_callback(...)` is called inside `with lock:`. Fix each with snapshot-then-release:
1. "Generating" status (~line 1226)
2. "Completed"/"Failed" after result (~line 1249)
3. Exception handler (~line 1268)

Pattern: read counters under lock, call callback outside lock.

## Full Audit Reference

The session produced a comprehensive 60-item audit of the entire codebase. The full findings table was in the previous plan file version. Key categories:
- **HIGH (9 items):** Missing .gitignore, 3 thread safety bugs, dead ModelFetcher, duplicate upload_to_freeimage, hardcoded API key, inconsistent warning color, missing default config keys
- **MEDIUM (~25 items):** Elapsed-time calc, O1 param remap, race conditions, non-atomic cache, type annotations, log unbounded growth, theme duplication, UX polish
- **LOW (~25 items):** Dead imports, inline imports, README issues, f-string logger perf, prompt slot alignment

The user chose to fix HIGH items first, then moved to B6+B7 (MEDIUM). The HIGH items that were planned (but may not all be implemented in code yet):
1. `.gitignore` — create
2. Thread safety: `_on_item_complete` → wrap with `root.after()`
3. Thread safety: `_memory_cache` → add `threading.Lock`
4. Dead `ModelFetcher.fetch_models()` → delete
5. Freeimage guest key → extract to constant
6. Duplicate `upload_to_freeimage` → consolidate via `fal_utils`

## Next Action

1. **Read the plan file:** `C:\Users\d0nbxx\.claude\plans\spicy-snuggling-cocke.md`
2. **Read `kling_generator_falai.py`** to check current state (may have partial changes from failed attempt)
3. **Implement B6:** Add lock + reservation set in `__init__`, rewrite `get_output_filename()`, add `discard()` calls
4. **Implement B7:** Refactor 3 progress_callback sites to snapshot-then-release
5. **Verify:** `python -m py_compile kling_generator_falai.py`

---

## Resume Instructions

To continue this work in a fresh session:

```
Read handoffs/2026-03-02_0935_b6-b7-concurrency-fixes.md and resume the work.

CRITICAL:
- Check "User Emphasis (IMPORTANT)" first - these are things I had to repeat.
- Check "DO NOTs & Constraints" to avoid regressions.
- Read the plan file at C:\Users\d0nbxx\.claude\plans\spicy-snuggling-cocke.md for detailed implementation steps.
- Read kling_generator_falai.py FIRST to check for partial/broken changes before editing.
- Start with "Next Action".
```
