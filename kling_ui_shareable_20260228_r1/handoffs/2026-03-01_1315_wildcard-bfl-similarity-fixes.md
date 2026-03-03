# Session Handoff: Wildcard Mode, BFL API, Similarity Scoring Fixes
Created: 2026-03-01 13:15

---

## Goal
Implement a plan with 4 deliverables for the selfie generation tab:
1. Fix DeepFace similarity label format
2. Add wildcard prompt mode (`{opt1|opt2}` random resolution)
3. Add BFL (Black Forest Labs) API support (3 models)
4. Fix underlying issues found during testing

## Goal Clarifications
- The wildcard template box IS the prompt input for wildcard mode — user enters their full prompt there with `{option|option}` blocks inline
- BFL API requires specific field names (`input_image` not `image`) and data URI prefix (`data:image/jpeg;base64,...`)
- Similarity scoring formula was fundamentally broken — 0% for visually similar faces is a bug, not "expected model behavior"
- Z-Image Turbo at strength 0.6 doesn't transform composition enough — passport photo stays looking like passport photo

## User Emphasis (IMPORTANT)
- ⚠️ **0% similarity is a BUG, not expected behavior.** User strongly corrected me for dismissing 0% similarity on Z-Image Turbo output as "expected." If the generated face visually resembles the source, the score must reflect that — not cliff-drop to 0%.
- ⚠️ **Models must actually follow the prompt.** The whole point is transforming a passport photo INTO a natural selfie. If the output keeps the passport composition, the model/settings failed. Don't dismiss this as "model limitation."
- ⚠️ **Test with the actual source image** — `F:\Downloads\Telegram Desktop\DLs\samantha-portrait.png` is a passport-style PNG with RGBA mode (alpha channel). This tripped the BFL JPEG encoding.

## Current State
- **Status:** In-progress — 3 commits pushed to PR, needs re-testing
- **What's done:**
  - DeepFace labels: `"Model (Sim: XX%)"` format ✅
  - Wildcard mode: radio toggle, template widget, resolve_wildcards(), config persistence ✅
  - BFL models: 3 models added (Kontext Pro, Kontext Max, FLUX 2 Pro) ✅
  - BFL API: correct `input_image` field, data URI prefix, RGBA→RGB conversion ✅
  - Similarity formula: rescaled over 2x threshold for graceful degradation ✅
  - Z-Image Turbo: strength bumped 0.6 → 0.85 ✅
- **What's pending/needs verification:**
  - BFL generation has NOT been verified end-to-end (user had API key set but all 3 failed due to the payload bugs we fixed)
  - Similarity scoring change needs visual verification — does 2x threshold give sensible percentages?
  - Z-Image Turbo at 0.85 strength needs testing — does it actually transform the composition now?
  - Wildcard mode resolved correctly in logs but generation quality with wildcard prompts untested across models
- **Active file(s):**
  - `selfie_generator.py` — main generator with BFL + similarity + wildcards
  - `kling_gui/tabs/selfie_tab.py` — UI with mode toggle + BFL key validation
  - `kling_gui/main_window.py` — config defaults + BFL badge

## Key Decisions
- **Similarity formula**: `(1 - distance / (threshold * 2)) * 100` — distance=0→100%, threshold→50%, 2*threshold→0%. This prevents the cliff-drop at threshold boundary.
- **BFL image encoding**: JPEG at quality 90, thumbnailed to 1024x1024 max, with `data:image/jpeg;base64,` prefix. RGBA/P/LA modes converted to RGB first.
- **BFL polling**: 5-second intervals, max 120 polls (10 min timeout). Status values: Pending/Ready/Error (capitalized per BFL docs).
- **Provider dispatch**: `generate()` checks `model.get("provider", "fal")` and routes to `_generate_fal_raw()` or `_generate_bfl_raw()`. Shared post-processing (similarity + rename) runs after either.
- **Z-Image Turbo strength 0.85**: High enough to significantly reshape composition per prompt, may lose some identity fidelity as tradeoff.

## Files Modified
- `selfie_generator.py` — Added: `resolve_wildcards()`, 3 BFL models with `"provider": "bfl"`, `_generate_bfl_raw()`, `_generate_fal_raw()` (extracted from old `generate()`), `_bfl_download()`, `_get_model_provider()`. Fixed: similarity formula (2x threshold scaling), Z-Image Turbo strength (0.6→0.85), RGBA→RGB conversion, BFL field name (`input_image`), `bfl_api_key` constructor param.
- `kling_gui/tabs/selfie_tab.py` — Added: `DEFAULT_WILDCARD_TEMPLATE`, `_prompt_mode_var`, mode toggle radio buttons, `_wildcard_frame` + `_wildcard_text`, `_apply_prompt_mode_ui()`, `_on_prompt_mode_changed()`, `_on_reset_wildcard_template()`, per-provider API key validation. Fixed: `_format_selfie_label()` and `_on_complete()` label format. Renamed models frame "Step 2 Models". Updated `get_config_updates()` with `selfie_prompt_mode` + `selfie_wildcard_template`.
- `kling_gui/main_window.py` — Added: `bfl_api_key` in default config, BFL badge in `keys_config`, 3 BFL endpoints in `selfie_selected_models` defaults.

## Active PRs
- **PR #4:** "feat(selfie): wildcard prompt mode, BFL API, label fix" - **open** - base: `fix/gui-fixes-distributable`
  - Branch: `feat/wildcard-mode-bfl-api`
  - 3 commits: `5918df8` (initial), `1fe5a06` (BFL payload fix), `7f4a9eb` (similarity + strength fix)
  - URL: https://github.com/aaronvstory/selfie-gen-ultimate/pull/4

## DO NOTs & Constraints
- ❌ **DO NOT dismiss 0% similarity as "expected"** — it's a scoring formula issue, not model behavior
- ❌ **DO NOT use `"image"` for BFL payloads** — the field is `"input_image"` per BFL docs
- ❌ **DO NOT save RGBA images as JPEG** — always convert to RGB first
- ❌ **DO NOT use old similarity formula** `(1 - distance/threshold)` — it cliff-drops at threshold
- ⚠️ **Constraint:** BFL result URLs expire in 10 minutes — download immediately after Ready status
- ⚠️ **Constraint:** Source images may be RGBA PNGs (passport photos from Telegram) — always handle alpha channel
- ⚠️ **Constraint:** No test suite — verify by running the GUI manually

## Relevant Artifacts

BFL API docs confirm correct field names:
- POST `https://api.bfl.ai/v1/flux-kontext-pro` with `{"prompt": "...", "input_image": "data:image/jpeg;base64,..."}`
- Response: `{"id": "...", "polling_url": "..."}`
- Poll result: `{"status": "Ready", "result": {"sample": "https://..."}}`

User's wildcard prompt template (what they entered in the wildcard box):
```
Transform this passport photo into a natural selfie: A person wearing a {black|gray|white|maroon|navy} t-shirt, taking a front-facing camera selfie with one arm FULLY extended but phone not visible in frame, looking directly at camera with a warm, natural smile. Shot in portrait orientation zoomed out to show head SLIGHTLY OFF-CENTER, with extensive space around all sides. Full torso visible with significant background space above and around subject. Background: {sunny backyard patio|cozy kitchen|home office|living room couch|coffee shop window}. Lighting: natural lighting. Authentic front-facing iPhone X camera quality, natural skin imperfections, uneven lighting, slightly off-center composition. Include realistic flaws: minor focus issues, natural skin texture with EVIDENT pores and minimal makeup, casual messy hair, wrinkled clothing, candid expression. Other arm relaxed at side, natural one-handed selfie pose. Maintain EXACT facial features, bone structure, and identity from reference image. Raw unfiltered AMATEUR smartphone selfie aesthetic with imperfect framing and natural shadows.
```

## Next Action
1. **Re-test BFL models** — Launch GUI, load samantha-portrait.png, toggle to Wildcards mode, select BFL Kontext Pro, generate. Verify the BFL submit/poll/download pipeline works end-to-end now.
2. **Verify similarity scores** — Check that the 2x threshold formula gives sensible percentages (should see 40-70% range for same-person outputs, not 0%).
3. **Verify Z-Image Turbo** — Test with the wildcard prompt at strength 0.85 — does it actually change the composition to look like a selfie?
4. **If BFL still fails**, check the error message in the GUI log — the improved error reporting now shows the HTTP response body.

---

## Resume Instructions

To continue this work in a fresh session:

```
Read handoffs/2026-03-01_1315_wildcard-bfl-similarity-fixes.md and resume the work.

CRITICAL:
- Check "User Emphasis (IMPORTANT)" first - these are things I had to repeat.
- Check "DO NOTs & Constraints" to avoid regressions.
- Start with "Next Action".
```
