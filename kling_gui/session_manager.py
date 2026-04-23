"""Session persistence helpers for GUI save/load/autosave."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import List, NamedTuple, Optional

logger = logging.getLogger(__name__)


class SessionRecord(NamedTuple):
    name: str
    path: str
    timestamp: str
    image_count: int


def _get_sessions_dir(app_dir: str) -> str:
    sessions_dir = os.path.join(app_dir, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    return sessions_dir


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name).strip("_")[:80] or "session"


def _walk_up_past_gen_folders(path: str) -> str:
    """Resolve project folder above generated output folders."""
    try:
        from path_utils import _walk_up_past_gen_folders as impl  # type: ignore

        return impl(path)
    except Exception:
        current = os.path.abspath(os.path.dirname(path))
        while True:
            name = os.path.basename(current).lower()
            if name not in {"gen-images", "gen-videos"}:
                return current
            parent = os.path.dirname(current)
            if parent == current:
                return current
            current = parent


def _resolve_session_folder(image_session) -> str:
    ref = getattr(image_session, "reference_entry", None)
    if ref:
        path = getattr(ref, "path", None)
    else:
        inputs = getattr(image_session, "input_images", None) or []
        if inputs:
            path = getattr(inputs[0][1], "path", None)
        else:
            images = getattr(image_session, "images", None) or []
            path = getattr(images[0], "path", None) if images else None

    if not path:
        return "untitled"

    project_dir = _walk_up_past_gen_folders(path)
    folder_name = os.path.basename(project_dir).strip()
    return folder_name or "untitled"


def get_autosave_path(app_dir: str, image_session) -> str:
    sessions_dir = _get_sessions_dir(app_dir)
    safe_name = _sanitize_name(_resolve_session_folder(image_session))
    return os.path.join(sessions_dir, f"{safe_name}_autosave.json")


def _derive_session_name(image_session) -> str:
    folder_name = _resolve_session_folder(image_session)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{_sanitize_name(folder_name)}_{timestamp}"


def list_sessions(app_dir: str) -> List[SessionRecord]:
    sessions_dir = _get_sessions_dir(app_dir)
    records: List[SessionRecord] = []

    for filename in os.listdir(sessions_dir):
        if not filename.endswith(".json"):
            continue
        file_path = os.path.join(sessions_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            session_data = data.get("session", {})
            image_count = len(session_data.get("images", [])) if isinstance(session_data, dict) else 0
            records.append(
                SessionRecord(
                    name=data.get("name", filename),
                    path=file_path,
                    timestamp=data.get("timestamp", ""),
                    image_count=image_count,
                )
            )
        except Exception:
            logger.warning("Skipping corrupt session file: %s", filename)

    records.sort(key=lambda r: r.timestamp, reverse=True)
    return records


def save_session(
    app_dir: str,
    image_session,
    config: dict,
    name: Optional[str] = None,
    overwrite_path: Optional[str] = None,
) -> str:
    sessions_dir = _get_sessions_dir(app_dir)
    session_name = name or _derive_session_name(image_session)

    data = {
        "name": session_name,
        "timestamp": datetime.now().isoformat(),
        "session": image_session.to_dict(),
        "config_snapshot": {
            key: config.get(key)
            for key in (
                "selfie_selected_models",
                "selfie_prompt_template",
                "selfie_scene_templates",
                "selfie_prompt_mode",
                "selfie_wildcard_template",
                "selfie_id_weight",
                "selfie_width",
                "selfie_height",
            )
            if config.get(key) is not None
        },
    }

    file_path = overwrite_path or ""
    if file_path and os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            data["name"] = existing.get("name", session_name)
        except Exception:
            pass
    else:
        safe = _sanitize_name(session_name)
        file_path = os.path.join(sessions_dir, f"{safe}.json")
        counter = 2
        while os.path.exists(file_path):
            file_path = os.path.join(sessions_dir, f"{safe}_{counter}.json")
            counter += 1

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Session saved: %s", file_path)
    return file_path


def load_session(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_session(path: str) -> None:
    if os.path.isfile(path):
        os.remove(path)
        logger.info("Session deleted: %s", path)
