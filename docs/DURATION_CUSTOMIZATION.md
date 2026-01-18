# Duration Customization Feature

## Overview

This feature allows users to select custom video durations from model-specific options, with comprehensive validation to prevent invalid API requests.

## Key Components

### 1. Model Metadata (`model_metadata.py`)
Centralized model configuration to avoid duplication:
- `MODEL_METADATA`: List of all supported models with duration options
- `get_model_by_endpoint()`: Retrieve model info by endpoint
- `get_duration_options()`: Get valid durations for a model
- `get_duration_default()`: Get default duration for a model

### 2. Validation (`kling_gui/queue_manager.py`)
Priority-based pattern matching for accurate validation:
- `MODEL_DURATION_CONSTRAINTS`: Priority-ordered pattern list
- `validate_duration()`: Validates duration against model constraints
- `get_duration_options_for_model()`: Helper to get valid options

### 3. GUI Controls (`kling_gui/config_panel.py`)
Duration selector with dynamic updates:
- Duration dropdown in Row 8 (Video Settings)
- Auto-updates when model changes
- Syncs with config and display label

### 4. CLI Enhancement (`kling_automation_ui.py`)
Improved duration prompts with validation:
- Shows common duration options
- Warns about uncommon durations
- Validates user input

## Supported Models & Durations

| Model | Durations | Default |
|-------|-----------|---------|
| Kling 2.1 Professional | 5s, 10s | 5s |
| Kling 2.5 Turbo Pro | 5s, 10s | 5s |
| Kling O1 | 5s, 10s | 5s |
| Wan 2.5 | 5s, 10s | 5s |
| **Wan 2.6** | **5s, 10s, 15s** | **5s** |
| Veo 3 | 5s, 6s, 7s, 8s | 5s |
| Ovi | 5s, 10s | 5s |
| LTX-2 | 5s, 10s | 5s |
| Pixverse V5 | 5s, 8s | 5s |
| **Pixverse V5.5** | **5s, 8s, 10s** | **5s** |
| Hunyuan Video | 5s, 10s | 5s |
| MiniMax Video | 6s | 6s |
| **Vidu Q2** | **2s-8s** | **4s** |

**Bold** = New or extended duration support

## Validation Rules

1. **Priority Matching**: More specific patterns matched first
   - Example: "pixverse/v5.5" before "pixverse/v5"
   
2. **Positive Integers Only**: Duration must be > 0

3. **Graceful Degradation**: Unknown models log warning but allow

4. **Clear Error Messages**: Shows allowed durations on validation failure

## Usage Examples

### GUI
1. Select model from dropdown
2. Duration options auto-update
3. Choose from available durations
4. Queue processes with validation

### CLI
```python
# Automatic validation during custom endpoint setup
Enter duration in seconds (5, 10, default 10): 15
⚠ Uncommon duration 15s - verify model supports this
```

### Programmatic
```python
from kling_gui.queue_manager import validate_duration, get_duration_options_for_model

# Get options for a model
options = get_duration_options_for_model("fal-ai/wan/v2.6/image-to-video")
# Returns: [5, 10, 15]

# Validate before API call
validate_duration("fal-ai/wan/v2.6/image-to-video", 15)  # OK
validate_duration("fal-ai/wan/v2.6/image-to-video", 20)  # ValueError
```

## Testing

### Run Tests
```bash
# Validation tests (28 tests total)
python test_duration_validation.py

# Metadata structure tests
python test_model_metadata.py
```

### Test Coverage
- ✅ 23 validation tests (all models + edge cases)
- ✅ 5 helper function tests
- ✅ 13 metadata structure tests
- ✅ Negative/zero duration tests
- ✅ Unknown model graceful degradation

## Architecture Improvements

### Before
- ❌ Duplicated metadata in 2 files
- ❌ Simple substring matching
- ❌ Limited error messages
- ❌ No helper functions

### After
- ✅ Centralized metadata module
- ✅ Priority-based pattern matching
- ✅ Comprehensive error messages with model names
- ✅ Helper functions for duration options
- ✅ Better error handling with rollback
- ✅ Edge case validation (negative, zero)

## Future Enhancements

1. **API-Driven Metadata**: Fetch duration options from fal.ai API
2. **Custom Duration Input**: Allow text entry for experimental durations
3. **Duration Presets**: Save favorite duration configurations
4. **Batch Duration Override**: Set different durations per queue item

## Technical Notes

### Pattern Matching Priority
```python
# Higher priority = more specific
("kling-video/v2.5", [5, 10], 3)  # Checked before...
("kling-video/v2", [5, 10], 2)    # ...this generic pattern
```

### Error Handling Flow
1. Duration validation fails
2. ValueError raised with allowed durations
3. GUI catches error, reverts to previous value
4. User sees notification with valid options

### Backward Compatibility
- Old configs without duration use defaults
- Legacy `duration` field supported via fallback
- Existing videos not affected
