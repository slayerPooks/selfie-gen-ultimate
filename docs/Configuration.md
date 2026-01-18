# Configuration Schema

The application settings are stored in `kling_config.json`. This file is automatically created on the first run.

## Example `kling_config.json`

```json
{
  "falai_api_key": "your-key-here",
  "output_folder": "C:/Videos",
  "use_source_folder": true,
  "current_model": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
  "model_display_name": "Kling 2.5 Turbo Pro",
  "current_prompt_slot": 2,
  "saved_prompts": {
    "1": "Basic animation",
    "2": "Enhanced lifelike movements",
    "3": null
  },
  "video_duration": 10,
  "loop_videos": false,
  "allow_reprocess": true,
  "reprocess_mode": "increment",
  "verbose_logging": true,
  "duplicate_detection": true
}
```

## Key Parameters

| Parameter | Description |
|-----------|-------------|
| `falai_api_key` | Your authentication token for the fal.ai platform. |
| `current_model` | The specific Kling model endpoint being used. |
| `current_prompt_slot` | Which of the saved prompts to use for generations. |
| `video_duration` | Duration of generated video (default is 10s). |
| `loop_videos` | If true, creates a ping-pong loop using FFmpeg. |
| `reprocess_mode` | `overwrite` (replace existing) or `increment` (save as _2, _3). |
| `duplicate_detection` | If enabled, prevents starting a task for an image already in progress. |

## Prompt Slots
The application supports up to 10 saved prompt slots. Slot 2 is recommended for enhanced lifelike animation. You can edit these in the GUI Config Panel or the CLI settings menu.
