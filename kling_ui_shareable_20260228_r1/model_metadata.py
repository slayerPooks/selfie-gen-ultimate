"""
Shared model metadata for video generation models.

The model list is loaded from models.json (next to this file) so it can be
updated without touching source code.  Falls back to a hardcoded list only
when models.json is missing.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded fallback — used ONLY when models.json is missing
# ---------------------------------------------------------------------------
_FALLBACK_MODELS = [
    {
        "name": "Kling 2.5 Turbo Pro",
        "endpoint": "fal-ai/kling-video/v2.5/turbo-pro/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Fast turbo video generation",
    },
    {
        "name": "Kling 2.1 Professional",
        "endpoint": "fal-ai/kling-video/v2.1/pro/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Professional quality video generation",
    },
    {
        "name": "Hunyuan Video (Base)",
        "endpoint": "fal-ai/hunyuan-video/image-to-video",
        "duration_options": [5, 10],
        "duration_default": 5,
        "description": "Tencent Hunyuan video model",
    },
    {
        "name": "MiniMax Video (Base)",
        "endpoint": "fal-ai/minimax-video/image-to-video",
        "duration_options": [6],
        "duration_default": 6,
        "description": "MiniMax video generation",
    },
]


def _load_models_from_file() -> list:
    """Load model list from models.json next to this file.

    Returns the models list on success, or _FALLBACK_MODELS if the file is
    missing, malformed, or empty.
    """
    models_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")
    if not os.path.exists(models_path):
        logger.debug("models.json not found at %s — using fallback list", models_path)
        return _FALLBACK_MODELS

    try:
        with open(models_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        models = data.get("models", [])
        if not models:
            logger.warning("models.json has no 'models' list — using fallback")
            return _FALLBACK_MODELS
        # Validate minimum required fields
        valid = [m for m in models if m.get("name") and m.get("endpoint")]
        if not valid:
            logger.warning("models.json has no valid entries — using fallback")
            return _FALLBACK_MODELS
        logger.debug("Loaded %d models from models.json", len(valid))
        return valid
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load models.json (%s) — using fallback", exc)
        return _FALLBACK_MODELS


# ---------------------------------------------------------------------------
# Public model list — imported by config_panel and other modules
# ---------------------------------------------------------------------------
MODEL_METADATA = _load_models_from_file()


# ---------------------------------------------------------------------------
# Display-name helper
# ---------------------------------------------------------------------------

def get_model_display_name(model: dict) -> str:
    """Build the dropdown label for a model.

    Format (when release/cost are available):
        "Kling 3.0 Pro (Feb 2026), ~$2.80"

    Falls back gracefully when those fields are absent (e.g. API-fetched models).
    """
    name = model.get("name", "Unknown Model")
    release = model.get("release", "")
    cost = model.get("est_cost_10s", "")

    if release and cost:
        return f"{name} ({release}), ~{cost}"
    if release:
        return f"{name} ({release})"
    if cost:
        return f"{name}, ~{cost}"
    return name


# ---------------------------------------------------------------------------
# Convenience lookups (unchanged API)
# ---------------------------------------------------------------------------

def get_model_by_endpoint(endpoint: str) -> dict:
    """Return a copy of the model dict matching `endpoint`, or None."""
    for model in MODEL_METADATA:
        if model.get("endpoint") == endpoint:
            return model.copy()
    return None


def get_duration_options(endpoint: str) -> list:
    """Valid duration values (seconds) for the given endpoint."""
    model = get_model_by_endpoint(endpoint)
    if model:
        return model.get("duration_options", [5, 10])
    return [5, 10]


def get_duration_default(endpoint: str) -> int:
    """Default duration (seconds) for the given endpoint."""
    model = get_model_by_endpoint(endpoint)
    if model:
        return model.get("duration_default", 5)
    return 5
