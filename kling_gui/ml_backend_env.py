"""Shared ML backend environment bootstrap for TensorFlow/Keras compatibility."""

from __future__ import annotations

import os


def ensure_ml_backend_env() -> None:
    """Set compatibility env vars once without overriding explicit user values."""
    if not os.environ.get("TF_USE_LEGACY_KERAS"):
        os.environ["TF_USE_LEGACY_KERAS"] = "1"
    if not os.environ.get("KERAS_BACKEND"):
        os.environ["KERAS_BACKEND"] = "tensorflow"
