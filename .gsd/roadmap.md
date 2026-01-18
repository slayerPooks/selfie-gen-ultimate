# GSD Project Roadmap: Seedance 1.5 Pro Advanced Parameters

## Project Overview
Add advanced generation parameters (first/last frame, aspect ratio, resolution, duration, camera, seed, audio) to both CLI and GUI for fal.ai video generation models, with focus on Seedance 1.5 Pro. Also expand prompt slots from 3 to 10.

## API Research Summary (Seedance 1.5 Pro)
Based on fal.ai documentation analysis:

| Parameter | API Name | Type | Values | Default |
|-----------|----------|------|--------|---------|
| First Frame | `image_url` | URL (required) | Any image URL | - |
| Last Frame | `end_image_url` | URL (optional) | Any image URL | null |
| Aspect Ratio | `aspect_ratio` | String | 21:9, 16:9, 4:3, 1:1, 3:4, 9:16 | 16:9 |
| Resolution | `resolution` | String | 480p, 720p | 720p |
| Duration | `duration` | Integer | 4-12 seconds | 5 |
| Camera Fixed | `camera_fixed` | Boolean | true/false | false |
| Seed | `seed` | Integer | Any or -1 for random | -1 |
| Audio | `generate_audio` | Boolean | true/false | true |

**Note:** Resolution caps at 720p (not 1080p) for this model.

---

## Milestone 1: Configuration Schema & Persistence
**Priority:** High | **Status:** Pending

Extend the config schema to store all new parameters and expand prompt slots.

### Phases:
1. **Config Schema Update** - Add new fields to default config in both CLI and GUI
2. **Persistence Layer** - Ensure proper save/load with defaults and migrations
3. **Prompt Slots Expansion** - Expand from 3 slots to 10 slots

### Acceptance Criteria:
- [ ] Config schema includes all new parameters
- [ ] Backward compatibility with existing config files
- [ ] 10 prompt slots available and persisted

---

## Milestone 2: API Integration
**Priority:** High | **Status:** Pending

Update `kling_generator_falai.py` to pass new parameters to fal.ai API.

### Phases:
1. **Parameter Passthrough** - Add all new params to `create_kling_generation()`
2. **Last Frame Upload** - Handle optional end_image_url upload
3. **Model Detection** - Detect which parameters each model supports
4. **API Payload Construction** - Build payload dynamically based on model capabilities

### Acceptance Criteria:
- [ ] All parameters passed to API when supported
- [ ] Last frame image upload works correctly
- [ ] Unsupported parameters gracefully ignored per model

---

## Milestone 3: GUI Implementation
**Priority:** High | **Status:** Pending

Add visual controls for all new parameters in the GUI config panel.

### Phases:
1. **Advanced Settings Panel** - Create expandable/collapsible section
2. **First/Last Frame Controls** - Drag-drop or browse for end frame
3. **Parameter Controls** - Dropdowns/sliders for aspect ratio, resolution, duration, etc.
4. **Seed Control** - Random toggle + manual entry field
5. **Audio Toggle** - Checkbox with model support indicator
6. **Prompt Slots UI** - Expand slot selector from 3 to 10

### Acceptance Criteria:
- [ ] All parameters configurable via GUI
- [ ] Visually polished integration matching existing design
- [ ] Controls show/hide based on model support
- [ ] Settings persist between sessions

---

## Milestone 4: CLI Implementation
**Priority:** Medium | **Status:** Pending

Add menu options for new parameters in CLI mode.

### Phases:
1. **Menu Extensions** - Add options to configuration menu
2. **Interactive Prompts** - User-friendly parameter selection
3. **Display Updates** - Show current settings in header/status

### Acceptance Criteria:
- [ ] All parameters configurable via CLI
- [ ] Current settings displayed in menu
- [ ] Changes persist correctly

---

## Milestone 5: Testing & Polish
**Priority:** Medium | **Status:** Pending

End-to-end testing and UI refinement.

### Phases:
1. **Integration Testing** - Test all parameter combinations
2. **Edge Cases** - Handle invalid inputs gracefully
3. **UI Polish** - Ensure visual consistency
4. **Documentation** - Update any help text

### Acceptance Criteria:
- [ ] All features work end-to-end
- [ ] No regressions in existing functionality
- [ ] Clean, polished UI

---

## Technical Notes

### Model Capability Detection
Different models support different parameters. The existing `model_capabilities` cache (used for negative_prompt detection) should be extended to detect all parameters by querying the model's OpenAPI schema.

### Default Behavior
When users "just want to start quickly":
- All new parameters default to current behavior
- Last frame: disabled (null)
- Aspect ratio: 9:16 (current default)
- Resolution: 720p
- Duration: 10s (current default)
- Camera fixed: false
- Seed: -1 (random)
- Audio: false (disabled)

### File Locations
- Config: `kling_config.json`
- Generator: `kling_generator_falai.py`
- GUI Config Panel: `kling_gui/config_panel.py`
- GUI Main Window: `kling_gui/main_window.py`
- CLI: `kling_automation_ui.py`

---

## Milestone 6: Dynamic Model Parameter Detection
**Priority:** Critical | **Status:** Pending

Implement robust dynamic parameter detection to replace hardcoded values, creating a `model_schema_manager.py` to manage capabilities.

### Phases:
1. **Model Schema Fetcher** - Query fal.ai Platform API on startup or model selection to populate `model_schema_manager.py`
2. **Parameter Registry** - Cache discovered parameters per model endpoint
3. **Dynamic UI Generation** - Show/hide controls in both GUI (`kling_gui`) and CLI (`kling_automation_ui.py`) based on model capabilities
4. **Request Validation** - Update `kling_generator_falai.py` to only include supported parameters in API payloads

### Acceptance Criteria:
- [ ] `model_schema_manager.py` successfully implemented
- [ ] Hardcoded parameters replaced with dynamic registry lookups
- [ ] UI adapts to different models automatically
- [ ] API requests validation logic in place
