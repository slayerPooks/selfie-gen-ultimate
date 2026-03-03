# Session Handoff: Carousel Redesign + UI Height Tweaks
Created: 2026-03-01 17:38

---

## Goal
Implement a split carousel (Reference vs Generated panels) with hover preview, then adjust text box heights and model checkbox area across all tabs for better usability.

## Goal Clarifications
- Carousel was a single flat list — user wanted original image always pinned, generated results in a separate section with thumbnails
- After carousel, user asked for taller text boxes across all tabs, especially the model checkbox area so scrolling isn't needed
- User also wanted the Subject/Style/Compose row removed from Selfie tab (JSON Handoff mode) — gender comes from JSON, style defaults to "candid"
- Outpaint "Expand Image" button had wrong font color (white on blue bg → should be black)
- Tab 4 (Video) is a known mess — user is fixing it in the original app and will port it later. **DO NOT touch tab 4.**

## User Emphasis (IMPORTANT)
- ⚠️ **Light blue bg = black font, always.** Convention: `bg=COLORS["accent_blue"]` → `fg="#111111"` (not white)
- ⚠️ **Tab 4 (Video) is off-limits** — user is fixing it in the original version and will port it in
- ⚠️ **Face Resemblance slider**: Only affects 3 of 12 models (PuLID, FLUX PuLID, Instant Character). Other 9 ignore it. Default is already 1.0 in config. User wants max resemblance.
- ⚠️ **Carousel outpaint bug**: User reported outpaint results not appearing in carousel. Fixed with re-entrancy guard + deferred refresh. Needs verification.
- ⚠️ **Expand tab layout is "awkward"** — user noted misaligned controls, button placement. Low priority but noted for future.

## Current State
- **Status:** in-progress (carousel + height changes done, needs testing)
- **What's done:**
  - Carousel redesign: split Reference/Generated panels, thumbnail strip, hover preview (0.5s delay → 600px popup)
  - `image_state.py`: Added `_reference_index`, `reference_entry`, `input_images`, `generated_images`, `navigate_reference()`
  - Text box heights increased across Prep, Selfie, Outpaint tabs
  - Models canvas height 98→140px (should show all models without scrolling)
  - Subject/Style/Compose row removed from Selfie tab JSON Handoff mode
  - Outpaint "Expand Image" button font color fixed
  - Re-entrancy guard added to carousel `_update_display()` to fix outpaint result not appearing
- **What's broken/pending:**
  - Carousel outpaint display bug — fix deployed but NOT yet verified by user
  - Tab 4 (Video) layout is messy — user will port fix from original app
  - Expand tab layout could use reorganization (user called it "nitpicky")
- **Active file(s):**
  - `kling_gui/carousel_widget.py` (full rewrite)
  - `kling_gui/image_state.py` (reference tracking additions)
  - `kling_gui/main_window.py` (minsize 150→200)
  - `kling_gui/tabs/selfie_tab.py` (heights, composer row removal)
  - `kling_gui/tabs/prep_tab.py` (vision prompt height 8→10)
  - `kling_gui/tabs/outpaint_tab.py` (prompt height 2→3, button color fix)

## Key Decisions
- **Carousel split layout**: Reference (top) + separator + Generated (bottom), both `expand=True` to split equally
- **Thumbnail strip**: 72px thumbnails, horizontal scrollable canvas with mouse wheel support, blue border on active
- **Hover preview**: 0.5s delay, borderless `Toplevel` up to 600px, clamped to screen edges
- **Composer row removal**: Gender var kept internally (config persistence), style hardcoded to "candid", Compose button dead code kept for now
- **Re-entrancy fix**: `_updating` bool flag wrapping `_update_display()` + 50ms deferred refresh after session changes

## Files Modified
- `kling_gui/image_state.py` — Added `_reference_index` field, `reference_entry`/`reference_index`/`input_images`/`generated_images` properties, `navigate_reference()` method, fixed `clear()`/`remove_current()` to handle reference index
- `kling_gui/carousel_widget.py` — **Full rewrite**: split Reference/Generated panels, thumbnail strip, hover preview popup, re-entrancy guard
- `kling_gui/main_window.py` — `carousel_frame` minsize 150→200
- `kling_gui/tabs/selfie_tab.py` — Removed Subject/Style/Compose row UI, scene templates 4→3 lines, wildcard template 6→7 lines, models canvas 98→140px, cleaned up `DEFAULT_CAMERA_STYLE` import
- `kling_gui/tabs/prep_tab.py` — Vision prompt height 8→10 lines
- `kling_gui/tabs/outpaint_tab.py` — Guidance prompt 2→3 lines, Expand button fg white→#111111

## Active PRs
None — all work is on branch `feat/wildcard-mode-bfl-api`

## DO NOTs & Constraints
- ❌ **DO NOT touch Tab 4 (Video tab / `video_tab.py`)** — User is fixing it in the original app and will port
- ❌ **DO NOT change `ImageSession.set_on_change()` to multi-callback** — only one consumer (carousel), keep it simple
- ❌ **DO NOT increase id_weight above 1.0** — PuLID models cap at 1.0 internally; Instant Character maps via `* 1.5` so 1.0 → 1.5 scale which is already high
- ⚠️ **Constraint:** No test suite — verify by launching GUI and testing the relevant tab
- ⚠️ **Constraint:** Pyright shows "could not resolve" for relative imports and runtime-only modules (selfie_generator, PIL) — these are expected and not real errors

## Relevant Artifacts

### Carousel re-entrancy fix (key snippet):
```python
def _update_display(self):
    if self._updating:
        return
    self._updating = True
    try:
        self._update_reference_panel()
        self._update_generated_panel()
    finally:
        self._updating = False
```

### Height changes summary:
| Tab | Widget | Before | After |
|-----|--------|--------|-------|
| Prep | Vision prompt | 8 lines | 10 lines |
| Selfie | Scene templates | 4 lines | 3 lines |
| Selfie | Wildcard template | 6 lines | 7 lines |
| Selfie | Models canvas | 98px | 140px |
| Outpaint | Guidance prompt | 2 lines | 3 lines |

## Next Action
1. **Verify carousel outpaint bug is fixed** — add an image, run outpaint, confirm the result appears in the GENERATED panel with thumbnail
2. **If user ports Tab 4 from original app** — help integrate it (will involve replacing `video_tab.py` and possibly `config_panel.py`, `queue_manager.py`)
3. **Expand tab layout cleanup** — user noted awkward alignment, low priority

---

## Resume Instructions

To continue this work in a fresh session:

```
Read handoffs/2026-03-01_1738_carousel-redesign-ui-heights.md and resume the work.

CRITICAL:
- Check "User Emphasis (IMPORTANT)" first - these are things I had to repeat.
- Check "DO NOTs & Constraints" to avoid regressions.
- Start with "Next Action".
```
