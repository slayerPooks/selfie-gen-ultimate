"""Tab package for the Portrait-to-Video Toolkit."""

import os
import sys

# Ensure the app root (parent of kling_gui/) is on sys.path so that
# top-level modules (vision_analyzer, selfie_generator, etc.) can be
# imported from within tab background threads — same pattern used by
# main_window.py, config_panel.py, queue_manager.py, and drop_zone.py.
_app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

from .prep_tab import PrepTab
from .selfie_tab import SelfieTab
from .outpaint_tab import OutpaintTab
from .video_tab import VideoTab

__all__ = ["PrepTab", "SelfieTab", "OutpaintTab", "VideoTab"]
