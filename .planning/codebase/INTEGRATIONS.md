# External Integrations

**Analysis Date:** 2026-01-14

## APIs & External Services

**AI Video Generation:**
- fal.ai Platform API - Primary video generation service
  - SDK/Client: Direct REST API via `requests` (`kling_generator_falai.py`)
  - Auth: API key stored in `kling_config.json` (falai_api_key field)
  - Endpoints used:
    - Queue: `https://queue.fal.run/{model_endpoint}` (job submission)
    - Models: `https://api.fal.ai/v1/models?category=image-to-video` (model listing)
    - Pricing: `https://api.fal.ai/v1/models/pricing` (cost estimation)
  - Request Flow: Submit job → Get request_id + status_url → Poll → Download

**Image Hosting:**
- freeimage.host - Temporary image hosting for public URLs
  - SDK/Client: REST API via `requests` (`kling_generator_falai.py:153-209`)
  - Auth: Guest API key hardcoded (`6d207e02198a847aa98d0a2a901485a5`)
  - Endpoint: `https://freeimage.host/api/1/upload`
  - Purpose: fal.ai requires public image URLs; local files uploaded here first

**Email/SMS:**
- Not applicable - Desktop application, no notification services

**External APIs:**
- None additional - All functionality via fal.ai and freeimage.host

## Data Storage

**Databases:**
- None - All data stored in JSON files

**File Storage:**
- Local filesystem only
- Configuration: `kling_config.json` (user settings)
- History: `kling_history.json` (processed files)
- Chrome profile: `chrome_profile/` (browser session for balance tracking)

**Caching:**
- In-memory caching for model list and pricing (`_cached_price`, `_cached_models`)
- Persisted model cache in `kling_config.json` (cached_models field)

## Authentication & Identity

**Auth Provider:**
- None - Direct API key authentication only
- fal.ai API key manually entered by user
- Stored unencrypted in `kling_config.json`

**OAuth Integrations:**
- None

## Monitoring & Observability

**Error Tracking:**
- Local logging only via Python `logging` module
- Crash logs: `kling_crash.log` (GUI mode)
- Debug logs: `kling_debug.log` (GUI mode)

**Analytics:**
- None

**Logs:**
- stdout/stderr for CLI mode
- File-based logging for GUI mode (`kling_gui/main_window.py`)

## CI/CD & Deployment

**Hosting:**
- Not applicable - Desktop application
- Distribution via `distribution/` folder (self-contained)

**CI Pipeline:**
- Not configured
- No GitHub Actions or CI files detected

## Environment Configuration

**Development:**
- Required: Python 3.8+, pip
- Required env vars: None (all config in JSON)
- Optional: Chrome browser, FFmpeg
- Setup: `pip install requests pillow rich selenium webdriver-manager tkinterdnd2`

**Staging:**
- Not applicable - Desktop application

**Production:**
- Same as development
- Users run `python kling_automation_ui.py` (CLI) or launch GUI
- `distribution/run_kling_ui.bat` creates venv automatically

## Webhooks & Callbacks

**Incoming:**
- None - Desktop application

**Outgoing:**
- None

## Supported AI Models (via fal.ai)

100+ models available, including:
- Kling (v1.0 - v2.6, Pro/Standard/Master/Turbo variants)
- Sora 2 (OpenAI)
- Veo 2/3/3.1 (Google DeepMind)
- LTX Video (various versions)
- Pixverse (v3.5 - v5.5)
- Hunyuan Video (Tencent)
- MiniMax/Hailuo (various versions)
- Wan (v2.1 - v2.6)
- Pika (v1.5 - v2.2)
- Luma Dream Machine/Ray 2

---

*Integration audit: 2026-01-14*
*Update when adding/removing external services*
