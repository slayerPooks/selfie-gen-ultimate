"""Session persistence — save / load / list / delete session snapshots."""

import os
import json
import re
import logging
from datetime import datetime
from typing import List, Optional, NamedTuple

logger = logging.getLogger(__name__)


class SessionRecord(NamedTuple):
    name: str
    path: str
    timestamp: str  # ISO format
    image_count: int


def _get_sessions_dir(app_dir: str) -> str:
    d = os.path.join(app_dir, "sessions")
    os.makedirs(d, exist_ok=True)
    return d


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name).strip("_")[:80] or "session"


def _derive_session_name(image_session) -> str:
    """Auto-derive a name from the first input image's parent folder + timestamp."""
    ref = image_session.reference_entry
    if ref:
        folder_name = os.path.basename(os.path.dirname(ref.path))
    else:
        images = image_session.images
        folder_name = os.path.basename(os.path.dirname(images[0].path)) if images else "untitled"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{_sanitize_name(folder_name)}_{ts}"


def list_sessions(app_dir: str) -> List[SessionRecord]:
    """Return all saved sessions, sorted newest-first."""
    sessions_dir = _get_sessions_dir(app_dir)
    records = []
    for fname in os.listdir(sessions_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(sessions_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append(SessionRecord(
                name=data.get("name", fname),
                path=fpath,
                timestamp=data.get("timestamp", ""),
                image_count=len(data.get("session", {}).get("images", [])),
            ))
        except Exception:
            logger.warning("Skipping corrupt session file: %s", fname)
    records.sort(key=lambda r: r.timestamp, reverse=True)
    return records


def save_session(
    app_dir: str,
    image_session,
    config: dict,
    name: Optional[str] = None,
    overwrite_path: Optional[str] = None,
) -> str:
    """Save session to JSON. Returns the saved file path.

    If overwrite_path is given, overwrites that file in place.
    Otherwise creates a new file (auto-increments on collision).
    """
    sessions_dir = _get_sessions_dir(app_dir)
    session_name = name or _derive_session_name(image_session)

    data = {
        "name": session_name,
        "timestamp": datetime.now().isoformat(),
        "session": image_session.to_dict(),
        "config_snapshot": {
            k: config.get(k)
            for k in (
                "selfie_selected_models",
                "selfie_prompt_template",
                "selfie_scene_templates",
                "selfie_prompt_mode",
                "selfie_wildcard_template",
                "selfie_id_weight",
                "selfie_width",
                "selfie_height",
            )
            if config.get(k) is not None
        },
    }

    if overwrite_path and os.path.isfile(overwrite_path):
        fpath = overwrite_path
        # Preserve original name from existing file
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                old = json.load(f)
            data["name"] = old.get("name", session_name)
        except Exception:
            pass
    else:
        safe = _sanitize_name(session_name)
        fpath = os.path.join(sessions_dir, f"{safe}.json")
        counter = 2
        while os.path.exists(fpath):
            fpath = os.path.join(sessions_dir, f"{safe}_{counter}.json")
            counter += 1

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Session saved: %s", fpath)
    return fpath


def load_session(path: str) -> dict:
    """Load a session file, returns the raw dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_session(path: str) -> None:
    """Delete a session file."""
    if os.path.isfile(path):
        os.remove(path)
        logger.info("Session deleted: %s", path)
