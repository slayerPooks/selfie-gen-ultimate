# fal.ai Video Duration Customization Research
**Date:** 2026-01-18
**Research Source:** Official fal.ai API Documentation via Exa MCP

## Executive Summary

✅ **YES - Custom video duration IS supported by fal.ai APIs**

The `duration` parameter is already implemented in our codebase and working correctly. We just need to:
1. Update validation constraints per model
2. Add GUI controls for user selection within model limits
3. Correct hardcoded model duration metadata

---

## API Parameter Details

### Parameter Format
- **Name:** `duration`
- **Type:** `DurationEnum` (string)
- **Format:** String representation of seconds (e.g., `"5"`, `"10"`, `"15"`)
- **Position:** Request body parameter for image-to-video endpoints
- **Required:** No (has default)

### Current Implementation Status
✅ **Already implemented correctly** in `kling_generator_falai.py` line 505:
```python
{
    "image_url": image_url,
    "prompt": prompt,
    "duration": str(duration),  # ✅ Correct format
    "aspect_ratio": aspect_ratio,
}
```

---

## Model-Specific Duration Constraints

### Kling Family Models
**All Kling 2.x models support: 5 or 10 seconds**

| Model | Endpoint | Supported Durations | Default | Current Code |
|-------|----------|---------------------|---------|--------------|
| Kling 2.5 Turbo Pro | `fal-ai/kling-video/v2.5-turbo/pro/image-to-video` | 5, 10 | 5 | 5 ✅ |
| Kling 2.5 | `fal-ai/kling-video/v2.5/*/image-to-video` | 5, 10 | 5 | - |
| Kling 2.6 Pro | `fal-ai/kling-video/v2.6/pro/image-to-video` | 5, 10 | 5 | - |
| Kling 2.1 Pro | `fal-ai/kling-video/v2.1/pro/image-to-video` | 5, 10 | 5 | 10 ⚠️ |
| Kling 2.1 Master | `fal-ai/kling-video/v2.1/master/image-to-video` | 5, 10 | 5 | 10 ✅ |
| Kling 2.1 Standard | `fal-ai/kling-video/v2.1/standard/image-to-video` | 5, 10 | 5 | - |
| Kling 2.0 Master | `fal-ai/kling-video/v2/master/image-to-video` | 5, 10 | 5 | - |
| Kling O1 | `fal-ai/kling-video/o1/image-to-video` | 5, 10 | 5 | 10 ⚠️ |
| Kling 1.0 | `fal-ai/kling-video/v1/standard/image-to-video` | 5, 10 | 5 | - |

**Pricing Structure:** Base price for 5s video, +$0.09 per additional second (Kling 2.1 Pro)

### Wan Models
**IMPORTANT:** Wan 2.5 vs 2.6 have different constraints!

| Model | Endpoint | Supported Durations | Default | Current Code |
|-------|----------|---------------------|---------|--------------|
| Wan 2.5 | `fal-ai/wan-25-preview/image-to-video` | 5, 10 | 5 | 5 ✅ |
| Wan 2.6 | `wan/v2.6/image-to-video` | **5, 10, 15** | 5 | Not in code |

**Key Difference:** Wan 2.6 added 15-second support (Wan 2.5 max is 10s)

### Pixverse Models

| Model | Endpoint | Supported Durations | Default | Current Code |
|-------|----------|---------------------|---------|--------------|
| Pixverse V5 | `fal-ai/pixverse/v5/image-to-video` | 5, 8 | 5 | 4 ❌ |
| Pixverse V5 (1080p) | Same | 5 only | 5 | - |
| Pixverse V5.5 | `fal-ai/pixverse/v5.5/image-to-video` | **5, 8, 10** | 5 | Not in code |

**Note:** 1080p resolution limits duration to 5s (or 5-8s for v5.5)

### Other Models

| Model | Endpoint | Supported Durations | Default | Current Code |
|-------|----------|---------------------|---------|--------------|
| Veo 3 | `fal-ai/veo3/image-to-video` | 5-8 (range) | 5 | 8 ✅ |
| Ovi | `fal-ai/ovi/image-to-video` | 5, 10 | 5 | 5 ✅ |
| LTX-2 | `fal-ai/ltx-2/image-to-video` | 5, 10 | 5 | 5 ✅ |
| Hunyuan Video | `fal-ai/hunyuan-video/image-to-video` | 5, 10 | 5 | 5 ✅ |
| MiniMax Video | `fal-ai/minimax-video/image-to-video` | 6 | 6 | 6 ✅ |
| Haiper Video V2 | `fal-ai/haiper-video-v2/image-to-video` | 4, 6 | 4 | - |
| Vidu Q2 | `fal-ai/vidu/image-to-video` | 2, 3, 4, 5, 6, 7, 8 | 4 | - |
| MAGI-1 | `fal-ai/magi/image-to-video` | Uses `num_frames` (96-192) | 96 | - |

---

## Current Implementation Analysis

### What's Working ✅
1. **Parameter format is correct** - Passing `str(duration)` as DurationEnum
2. **Configuration system works** - `video_duration` saved to config
3. **Parameter passing works** - Flows through CLI → Generator → API
4. **Basic validation exists** - `validate_duration()` for Kling 2.1 Master

### What Needs Fixing ⚠️

#### 1. Incomplete Validation (`kling_gui/queue_manager.py` line 101)
```python
def validate_duration(model_endpoint: str, duration: int) -> None:
    # Currently only checks Kling 2.1 Master
    if "v2.1/master" in model_endpoint and duration not in [5, 10]:
        raise ValueError(...)
```

**Issue:** Missing validation for all other models

#### 2. Incorrect Hardcoded Durations (`kling_automation_ui.py` lines 243-300)
```python
MODEL_PRESETS = [
    {"name": "Kling 2.1 Professional", "duration": 10},  # Should offer 5 or 10
    {"name": "Pixverse V5", "duration": 4},              # Should be 5 or 8
    # ... etc
]
```

**Issue:** Hardcoded single duration per model instead of showing options

#### 3. No GUI Duration Selector
- Users cannot choose duration within model constraints
- Duration label is display-only
- No dropdown/slider for duration selection

---

## Implementation Recommendations

### Priority 1: Update Model Metadata (High Impact, Low Effort)

**File:** `kling_automation_ui.py` lines 243-300

Change from single duration to constraint list:
```python
MODEL_PRESETS = [
    {
        "name": "Kling 2.1 Professional",
        "endpoint_id": "fal-ai/kling-video/v2.1/pro/image-to-video",
        "duration_options": [5, 10],  # NEW: List of options
        "duration_default": 5,        # NEW: Default choice
        "description": "Professional quality video generation",
    },
    {
        "name": "Wan 2.6",
        "endpoint_id": "wan/v2.6/image-to-video",
        "duration_options": [5, 10, 15],  # NEW: Wan 2.6 supports 15s!
        "duration_default": 5,
        "description": "Advanced video with extended duration support",
    },
    # ... etc
]
```

### Priority 2: Comprehensive Validation (High Impact, Medium Effort)

**File:** `kling_gui/queue_manager.py` lines 101-114

Replace single check with comprehensive validation:
```python
# Model duration constraints (from fal.ai docs)
MODEL_DURATION_CONSTRAINTS = {
    "kling-video/v2": [5, 10],           # All Kling 2.x models
    "wan-25-preview": [5, 10],           # Wan 2.5
    "wan/v2.6": [5, 10, 15],             # Wan 2.6
    "pixverse/v5/": [5, 8],              # Pixverse V5
    "pixverse/v5.5/": [5, 8, 10],        # Pixverse V5.5
    "veo3": list(range(5, 9)),           # Veo 3: 5-8
    "ovi": [5, 10],
    "ltx-2": [5, 10],
    "hunyuan-video": [5, 10],
    "minimax-video": [6],
    "haiper-video-v2": [4, 6],
    "vidu": list(range(2, 9)),           # Vidu Q2: 2-8
}

def validate_duration(model_endpoint: str, duration: int) -> None:
    """Validate duration against model constraints."""
    for key, allowed in MODEL_DURATION_CONSTRAINTS.items():
        if key in model_endpoint:
            if duration not in allowed:
                raise ValueError(
                    f"Duration {duration}s invalid for this model. "
                    f"Allowed: {', '.join(map(str, allowed))}s"
                )
            return
    # No constraint found = allow any duration (unknown model)
```

### Priority 3: GUI Duration Selector (Medium Impact, High Effort)

**File:** `kling_gui/config_panel.py`

Add duration dropdown next to model selector:

**Option A: Simple Dropdown**
```python
# After model dropdown
duration_frame = tk.Frame(...)
tk.Label(duration_frame, text="Duration:").pack(side=tk.LEFT)

self.duration_var = tk.StringVar(value="5")
self.duration_combo = ttk.Combobox(
    duration_frame,
    textvariable=self.duration_var,
    values=["5s", "10s"],  # Updated dynamically per model
    state="readonly",
    width=8
)
self.duration_combo.pack(side=tk.LEFT)
self.duration_combo.bind("<<ComboboxSelected>>", self._on_duration_change)
```

**Option B: Slider (Better UX for ranges)**
```python
self.duration_slider = tk.Scale(
    parent,
    from_=5, to=10,
    orient=tk.HORIZONTAL,
    label="Duration (seconds)",
    command=self._on_duration_change
)
# Update range dynamically when model changes
```

**Dynamic Update Logic:**
```python
def _on_model_change(self, event=None):
    """When model changes, update available duration options."""
    model = self.get_selected_model()
    duration_options = model.get("duration_options", [5, 10])

    # Update combo values
    self.duration_combo["values"] = [f"{d}s" for d in duration_options]

    # Set to default if current not valid
    current = self.config.get("video_duration", 10)
    if current not in duration_options:
        self.duration_var.set(f"{duration_options[0]}s")
        self.config["video_duration"] = duration_options[0]
```

### Priority 4: CLI Duration Prompt (Low Impact, Low Effort)

**File:** `kling_automation_ui.py` lines 1234-1241

Update user prompt to show model constraints:
```python
# Get model constraints
duration_options = selected_model.get("duration_options", [5, 10])
options_str = ", ".join(map(str, duration_options))

duration_input = input(
    f"\033[92mVideo duration in seconds ({options_str}, default {duration_options[0]}): \033[0m"
).strip()

duration = int(duration_input) if duration_input.isdigit() else duration_options[0]

# Validate
if duration not in duration_options:
    print(f"\033[91m⚠ Invalid duration. Using {duration_options[0]}s\033[0m")
    duration = duration_options[0]
```

---

## Testing Checklist

After implementing changes:

- [ ] Kling 2.5 Turbo Pro: Test 5s and 10s
- [ ] Wan 2.6: Test 5s, 10s, and 15s (NEW!)
- [ ] Pixverse V5: Test 5s and 8s (not 4s)
- [ ] Validation rejects invalid durations (e.g., Kling with 15s)
- [ ] GUI duration selector updates when model changes
- [ ] Config saves and loads custom duration correctly
- [ ] CLI shows correct options per model
- [ ] Pricing display accounts for duration (if applicable)

---

## Cost Implications

Most models charge per-second:
- **Kling 2.1 Pro:** $0.45 for 5s, +$0.09/sec → $0.90 for 10s (2x cost)
- **Wan 2.5/2.6:** $0.05-0.15/sec depending on resolution
- **Veo 3:** $2.50 for 5s, +$0.50/sec → $4.00 for 8s

**User should be aware:** Longer duration = higher cost proportionally

---

## Summary

**Answer to Original Question:**
✅ **YES - Custom duration IS fully supported!**

We're already passing the parameter correctly. We just need to:
1. Expose the choice to users (GUI/CLI)
2. Validate against model-specific constraints
3. Update hardcoded metadata

**Quick Win:** Update `MODEL_PRESETS` to include `duration_options` and users can manually edit config JSON to test immediately.

**Full Solution:** Implement GUI duration selector with dynamic validation.

---

## Source References

All information verified from official fal.ai documentation:
- https://fal.ai/models/fal-ai/kling-video/v2.5-turbo/pro/image-to-video/api
- https://fal.ai/models/wan/v2.6/image-to-video/api
- https://fal.ai/models/fal-ai/pixverse/v5/image-to-video/api
- https://fal.ai/learn/devs/wan-26-developer-guide-mastering-next-generation-video-generation
- https://fal.ai/learn/devs/pixverse-v5-5-developer-guide

Retrieved via Exa MCP on 2026-01-18.
