"""Shared theme constants for the Kling GUI."""

import sys


IS_MACOS = sys.platform == "darwin"

# Global font — change this one line to switch the entire UI typeface.
# Tk on macOS does not reliably resolve Windows font names.
FONT_FAMILY = "Helvetica" if IS_MACOS else "Segoe UI"
EMOJI_FONT_FAMILY = "Apple Color Emoji" if IS_MACOS else "Segoe UI Emoji"

# Unified color palette
COLORS = {
    # Base backgrounds
    "bg_main": "#2D2D30",
    "bg_panel": "#3C3C41",
    "bg_input": "#464649",
    "bg_hover": "#505055",

    # Text
    "text_light": "#DCDCDC",
    "text_dim": "#B4B4B4",
    "text_dark": "#111111",

    # Accents
    "accent_blue": "#6496FF",
    "border": "#5A5A5E",

    # Status
    "success": "#64FF64",
    "error": "#FF6464",
    "warning": "#FFA500",

    # Buttons
    "btn_green": "#329632",
    "btn_red": "#B43232",

    # Drop zone specific
    "bg_drop": "#464649",
    "drop_valid": "#329632",
    "drop_invalid": "#963232",

    # Verbose log colors
    "upload": "#00CED1",
    "task": "#87CEEB",
    "progress": "#FFD700",
    "debug": "#808080",
    "resize": "#DDA0DD",
    "download": "#98FB98",
    "api": "#DA70D6",

    # Config panel extras
    "text_unsupported": "#666666",
    "bg_unsupported": "#3A3A3A",
    "warning_light": "#FFB347",
}

# Native macOS Tk buttons can ignore dark backgrounds, so dark text keeps labels readable.
BUTTON_TEXT_COLOR = "#000000" if IS_MACOS else COLORS["text_light"]
BUTTON_FILLED_TEXT_COLOR = "#000000" if IS_MACOS else COLORS["text_light"]
BUTTON_DISABLED_TEXT_COLOR = "#666666"
