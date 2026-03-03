"""
Shared model metadata for video generation models.

The model list is loaded from models.json (next to this file) so it can be
updated without touching source code.  Supports two formats:
  - New (endpoint-only): models list contains endpoint strings
  - Legacy (dict): models list contains dicts with name, endpoint, etc.
Falls back to a hardcoded list only when models.json is missing.
"""

import json
import os
import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded fallback — used ONLY when models.json is missing
# ---------------------------------------------------------------------------
_FALLBACK_MODELS = [
    {"name": "Kling v2.5 Turbo Pro", "endpoint": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"},
    {"name": "MiniMax Video", "endpoint": "fal-ai/minimax-video/image-to-video"},
]


def _endpoint_to_short_name(endpoint: str) -> str:
    """Derive a readable display name from endpoint string as offline fallback.

    Examples:
        fal-ai/kling-video/v3/pro/image-to-video → Kling Video v3 Pro
        fal-ai/minimax-video/image-to-video → MiniMax Video
        fal-ai/hunyuan-video/v1.5/image-to-video → Hunyuan Video v1.5
    """
    if not endpoint:
        return "Unknown Model"

    # Remove prefix/suffix
    parts = (
        endpoint.replace("fal-ai/", "")
        .replace("/image-to-video", "")
        .replace("/video-to-video", "")
    )

    components = [p for p in parts.split("/") if p]
    if not components:
        return endpoint

    display_parts = []
    for comp in components:
        cleaned = comp.replace("-", " ").replace("_", " ")
        # Version number: keep lowercase v, capitalize rest
        if re.match(r"^v\d", cleaned):
            # e.g. "v2.5 turbo" → "v2.5 Turbo"
            sub_parts = cleaned.split()
            result = sub_parts[0]  # keep version as-is
            for sp in sub_parts[1:]:
                result += " " + sp.title()
            display_parts.append(result)
        elif cleaned.lower() == "o1":
            display_parts.append("O1")
        else:
            display_parts.append(cleaned.title())

    name = " ".join(display_parts)

    # Fix common brand capitalization
    name = name.replace("Minimax", "MiniMax")
    name = name.replace("Kling Video", "Kling Video")
    name = name.replace("Hunyuan Video", "Hunyuan Video")

    return name.strip()


def _load_models_from_file() -> list:
    """Load model list from models.json next to this file.

    Handles two formats:
      - New: models is a list of endpoint strings
      - Legacy: models is a list of dicts with name + endpoint

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
        models_raw = data.get("models", [])
        user_notes = data.get("user_notes", {})

        if not models_raw:
            logger.warning("models.json has no 'models' list — using fallback")
            return _FALLBACK_MODELS

        models = []
        for entry in models_raw:
            if isinstance(entry, str):
                # New format: just an endpoint string
                models.append({
                    "name": _endpoint_to_short_name(entry),
                    "endpoint": entry,
                    "user_notes": user_notes.get(entry, ""),
                })
            elif isinstance(entry, dict):
                # Legacy format: dict with name + endpoint (still works)
                if entry.get("name") and entry.get("endpoint"):
                    # Carry over user_notes if present in the map
                    ep = entry.get("endpoint", "")
                    if ep in user_notes and "user_notes" not in entry:
                        entry["user_notes"] = user_notes[ep]
                    models.append(entry)

        if not models:
            logger.warning("models.json has no valid entries — using fallback")
            return _FALLBACK_MODELS

        logger.debug("Loaded %d models from models.json", len(models))
        return models
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

    Supports three data sources (in priority order):
      1. API-sourced pricing (pricing_info dict with unit_price/unit)
      2. Legacy release/cost fields
      3. Name only

    Examples:
        "Kling Video v3 Pro, $2.24/10s"
        "Kling 3.0 Pro (Feb 2026), ~$2.24"
        "MiniMax Video, $0.50/video"
    """
    name = model.get("api_display_name") or model.get("name", "Unknown Model")

    # API-sourced pricing (from get_model_pricing enrichment)
    pricing = model.get("pricing_info", {})
    if pricing:
        unit = pricing.get("unit", "")
        price = pricing.get("unit_price", 0)
        if price:
            if unit == "second":
                cost_str = f"${price * 10:.2f}/10s"
            elif unit == "video":
                cost_str = f"${price:.2f}/video"
            elif unit == "image":
                cost_str = f"${price:.2f}/image"
            else:
                cost_str = f"${price:.2f}/{unit}" if unit else f"${price:.2f}"
            return f"{name}, {cost_str}"

    # Legacy format with release/cost
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

def get_model_by_endpoint(endpoint: str):
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


# ---------------------------------------------------------------------------
# Prompt length limits (from fal.ai OpenAPI schemas)
# ---------------------------------------------------------------------------

# Pattern-based limits: (substring_in_endpoint, max_chars)
_PROMPT_LIMITS = [
    ("minimax", 2000),
    ("kling-video/v3", None),     # v3 has no documented limit
    ("kling-video", 2500),        # v2.x / v1.x / O1
    ("hunyuan", 2500),            # not in schema but safe default
]

# Default fallback
_DEFAULT_PROMPT_LIMIT = 2500


def get_prompt_limit(endpoint: str) -> int:
    """Return the maximum prompt length (chars) for the given model endpoint.

    Returns None for models with no known limit.
    """
    ep = endpoint.lower()
    for pattern, limit in _PROMPT_LIMITS:
        if pattern in ep:
            return limit
    return _DEFAULT_PROMPT_LIMIT
