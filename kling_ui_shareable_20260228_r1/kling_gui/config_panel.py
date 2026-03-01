"""
Config Panel Widget - Model selection, output mode, and prompt editing.
With dynamic model fetching from fal.ai API.
"""

import tkinter as tk
from tkinter import ttk, filedialog
from typing import Callable, Optional, List, Dict
import threading
import time
import os
import re
import logging


# Color palette
COLORS = {
    "bg_main": "#2D2D30",
    "bg_panel": "#3C3C41",
    "bg_input": "#464649",
    "text_light": "#DCDCDC",
    "text_dim": "#B4B4B4",
    "accent_blue": "#6496FF",
    "border": "#5A5A5E",
    "warning": "#FFB347",
    "success": "#64FF64",
    "error": "#FF6464",
    "text_unsupported": "#666666",
    "bg_unsupported": "#3A3A3A",
}

# Import centralized model metadata to avoid duplication
from model_metadata import MODEL_METADATA, get_model_display_name

# Minimal fallback - ONLY used when API fails AND no cache exists
# Models change frequently - this is just a safety net with user's preferred model
# The app dynamically fetches all available models from fal.ai API
FALLBACK_MODELS = MODEL_METADATA

# fal.ai URLs for model browsing and API reference
FAL_MODELS_URL = "https://fal.ai/models?categories=image-to-video"
FAL_EXPLORE_URL = "https://fal.ai/explore/models"
FAL_API_DOCS_URL = "https://docs.fal.ai"

# Vague model names that should be replaced with parsed endpoint names
# Using frozenset for O(1) lookup performance
VAGUE_MODEL_NAMES = frozenset(
    ["kling video", "pixverse", "wan effects", "longcat video", "pika"]
)

# Precompiled regex patterns for word-boundary matching of vague names
# Compiled once at module load to avoid per-call compilation overhead
# Pattern: (?<!\w)name(?!\w) matches 'name' only when not surrounded by word characters
# e.g., 'pika' matches "Pika Video" but NOT "Pikachu Model"
VAGUE_MODEL_PATTERNS = {
    name: re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
    for name in VAGUE_MODEL_NAMES
}

# Global font — change this one line to switch the entire UI typeface.
# JetBrains Mono and Inter look great if installed; Segoe UI is the safe fallback.
FONT_FAMILY = "Segoe UI"

# UI Configuration
COMBOBOX_DROPDOWN_HEIGHT = 25  # Number of items visible in dropdown (default ~10)

# Module logger
logger = logging.getLogger(__name__)


def parse_endpoint_to_display_name(endpoint_id: str) -> str:
    """
    Parse fal.ai endpoint ID into a human-readable display name.

    Examples:
        fal-ai/kling-video/v2.5-turbo/pro/image-to-video → Kling v2.5 Turbo Pro
        fal-ai/kling-video/v2.6/pro/image-to-video → Kling v2.6 Pro
        fal-ai/veo3.1/image-to-video → Veo 3.1
        fal-ai/sora-2/image-to-video → Sora 2
    """
    if not endpoint_id:
        return "Unknown"

    # Remove common prefixes/suffixes
    parts = (
        endpoint_id.replace("fal-ai/", "")
        .replace("/image-to-video", "")
        .replace("/video-to-video", "")
    )

    # Split by / to get components
    components = [p for p in parts.split("/") if p]

    if not components:
        return endpoint_id

    # Build display name from components
    display_parts = []
    for comp in components:
        # Clean up component
        comp = comp.replace("-", " ").replace("_", " ")
        # Capitalize properly
        if comp.startswith("v") and any(c.isdigit() for c in comp):
            # Version number: v2.5-turbo → v2.5 Turbo
            display_parts.append(comp.replace(" ", "-").title().replace("-", " "))
        else:
            display_parts.append(comp.title())

    result = " ".join(display_parts)

    # Clean up common patterns
    result = result.replace("Kling Video", "Kling")
    result = result.replace("  ", " ")

    return result.strip()


class HoverTooltip:
    """Dark-themed floating tooltip shown when hovering a widget."""

    _BG = "#1A1A1E"
    _FG = "#DCDCDC"
    _BORDER = "#6496FF"
    _WRAP = 500  # px wraplength

    def __init__(self, widget: tk.Widget, text_func):
        """
        Args:
            widget: Widget that triggers the tooltip on hover.
            text_func: Callable() → str evaluated at show-time.
                       Empty/None string suppresses the popup.
        """
        self._widget = widget
        self._text_func = text_func
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        text = self._text_func()
        if not text or self._tip:
            return

        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)

        outer = tk.Frame(
            self._tip, bg=self._BG,
            highlightbackground=self._BORDER, highlightthickness=1,
        )
        outer.pack()
        tk.Label(
            outer, text=text,
            bg=self._BG, fg=self._FG,
            font=(FONT_FAMILY, 9),
            wraplength=self._WRAP, justify=tk.LEFT,
            padx=14, pady=10,
        ).pack(anchor="w")

        self._tip.update_idletasks()
        tip_w = self._tip.winfo_reqwidth()
        tip_h = self._tip.winfo_reqheight()

        wx = self._widget.winfo_rootx()
        wy = self._widget.winfo_rooty()
        wh = self._widget.winfo_height()
        sh = self._widget.winfo_screenheight()

        x = max(0, wx - tip_w + self._widget.winfo_width())
        y = wy + wh + 4
        if y + tip_h > sh - 40:
            y = wy - tip_h - 4  # flip above if near bottom of screen

        self._tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


class ModelFetcher:
    """Fetches available models from fal.ai API dynamically."""

    CACHE_TTL = 3600  # 1 hour cache (models don't change that often)

    @staticmethod
    def fetch_models(
        api_key: str, callback: Callable[[List[Dict], Optional[str]], None]
    ):
        """
        Fetch models in a background thread.

        Args:
            api_key: fal.ai API key
            callback: Called with (models_list, error_message) when done
        """

        def _fetch():
            try:
                import requests

                headers = {"Authorization": f"Key {api_key}"}
                all_models = []
                cursor = None

                # Paginate through all results
                while True:
                    params = {
                        "category": "image-to-video",
                        "status": "active",
                        "limit": 50,
                    }
                    if cursor:
                        params["cursor"] = cursor

                    response = requests.get(
                        "https://api.fal.ai/v1/models",
                        params=params,
                        headers=headers,
                        timeout=15,
                    )

                    if response.status_code != 200:
                        # Log detail for debugging but don't expose to user (may contain sensitive info)
                        detail = response.text[:200] if response.text else ""
                        logger.debug(
                            "Fal API error %s: %s", response.status_code, detail
                        )
                        callback([], f"API error {response.status_code}")
                        return

                    data = response.json()
                    for m in data.get("models", []):
                        endpoint_id = m.get("endpoint_id", "")
                        metadata = m.get("metadata", {})
                        api_display_name = metadata.get("display_name", "")

                        # Smart display name selection:
                        # 1. Check if API name is too vague (known problematic names)
                        # 2. Check if API name has version info (v2.5, 2.1, etc.)
                        # 3. If endpoint has version but API name doesn't, use parsed name
                        # Normalize for fuzzy checks (convert hyphens/underscores to spaces)
                        name_for_match = re.sub(r"[-_]+", " ", api_display_name).strip()

                        # Check if name matches a known vague pattern using precompiled regexes
                        # Patterns use word-boundary matching to avoid false positives
                        # e.g., 'pika' matches 'Pika Video' but not 'Pikachu Model'
                        is_vague = any(
                            pattern.search(name_for_match)
                            for pattern in VAGUE_MODEL_PATTERNS.values()
                        )

                        # Check if name has version info (v2, v2.5, 2.1, 1.6, etc.)
                        # Match: "v" followed by digits, OR digits with decimal (not "Video 01")
                        has_version_in_name = bool(
                            re.search(
                                r"\bv\d+(?:\.\d+)?", api_display_name, re.IGNORECASE
                            )
                            or re.search(
                                r"\b\d+\.\d+\b", api_display_name
                            )  # Like "2.1" or "1.6"
                        )

                        # Check if endpoint has version info
                        has_version_in_endpoint = bool(
                            re.search(r"/v\d+\.?\d*", endpoint_id)
                        )

                        # Use parsed name if: no API name, vague name, or endpoint has version but name doesn't
                        if (
                            not api_display_name
                            or is_vague
                            or (has_version_in_endpoint and not has_version_in_name)
                        ):
                            display_name = parse_endpoint_to_display_name(endpoint_id)
                        else:
                            display_name = api_display_name

                        all_models.append(
                            {
                                "name": display_name,
                                "endpoint": endpoint_id,
                                "duration": metadata.get("duration_estimate", 10),
                                "description": metadata.get("description", "")[:100],
                            }
                        )

                    # Check for more pages
                    if data.get("has_more") and data.get("next_cursor"):
                        cursor = data["next_cursor"]
                    else:
                        break

                if all_models:
                    # Sort models alphabetically by display name
                    all_models.sort(key=lambda m: m["name"].lower())
                    callback(all_models, None)
                else:
                    callback([], "No models found")

            except Exception as e:
                callback([], str(e))

        thread = threading.Thread(target=_fetch, daemon=True)
        thread.start()

    @staticmethod
    def get_cached_or_fallback(config: dict) -> List[Dict]:
        """Get cached models or fallback list."""
        cached = config.get("cached_models", {})
        cached_list = cached.get("models", [])
        cached_time = cached.get("timestamp", 0)

        # If cache exists, use it (even if stale - background refresh will update)
        # Only fall back if no cached models at all
        if cached_list:
            return cached_list

        return FALLBACK_MODELS

    @staticmethod
    def cache_models(config: dict, models: List[Dict]):
        """Save models to config cache."""
        config["cached_models"] = {"models": models, "timestamp": time.time()}


class ConfigPanel(tk.Frame):
    """Configuration panel for model, output, and prompt settings."""

    def __init__(
        self,
        parent,
        config: dict,
        on_config_changed: Callable[..., None],  # Flexible signature for compatibility
        build_prompt: bool = True,
        **kwargs,
    ):
        """
        Initialize the config panel.

        Args:
            parent: Parent widget
            config: Current configuration dict
            on_config_changed: Callback when config changes
            build_prompt: If False, prompt panel is not built inline — caller
                must call build_prompt_panel(parent) separately after init.
        """
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.config = config
        self.on_config_changed = on_config_changed
        self._build_prompt_inline = build_prompt

        # Configure dark theme for ttk Combobox widgets
        self._setup_combobox_style()

        self._setup_ui()
        self._load_config()

    def _setup_combobox_style(self):
        """Configure dark theme styling for ttk Combobox widgets."""
        style = ttk.Style(self)

        # Dark theme for all Combobox widgets in this panel
        style.configure(
            "Dark.TCombobox",
            fieldbackground=COLORS["bg_main"],
            background=COLORS["bg_input"],
            foreground=COLORS["text_light"],
            arrowcolor=COLORS["text_light"],
            borderwidth=0,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[
                ("readonly", COLORS["bg_main"]),
                ("disabled", COLORS["bg_panel"]),
            ],
            foreground=[
                ("readonly", COLORS["text_light"]),
                ("disabled", COLORS["text_dim"]),
            ],
            selectbackground=[("readonly", COLORS["accent_blue"])],
            selectforeground=[("readonly", "#FFFFFF")],
            arrowcolor=[
                ("disabled", COLORS["text_dim"]),
            ],
        )

        # Configure the dropdown listbox colors (affects all comboboxes)
        try:
            root = self.winfo_toplevel()
            root.option_add("*TCombobox*Listbox.background", COLORS["bg_main"])
            root.option_add("*TCombobox*Listbox.foreground", COLORS["text_light"])
            root.option_add(
                "*TCombobox*Listbox.selectBackground", COLORS["accent_blue"]
            )
            root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        except tk.TclError:
            pass  # Ignore if can't set listbox options

    def _setup_ui(self):
        """Set up the configuration UI — two-column layout."""
        self._prompt_edit_mode = False

        # Main config frame (no CONFIGURATION heading — spec item 5)
        config_frame = tk.Frame(self, bg=COLORS["bg_input"], padx=10, pady=10)
        config_frame.pack(fill=tk.X, padx=10, pady=(8, 10))
        self._config_frame = config_frame

        # ── Two-column layout from the top: left (model/output/options) | right (prompt) ──
        body_frame = tk.Frame(config_frame, bg=COLORS["bg_input"])
        body_frame.pack(fill=tk.BOTH, expand=True)

        # ── LEFT COLUMN: model row, output row, separator, then option rows ──────────────
        left_col = tk.Frame(body_frame, bg=COLORS["bg_input"])
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14), anchor="n")

        # Row 1: Model selection (in left_col so right column gets full panel height)
        row1 = tk.Frame(left_col, bg=COLORS["bg_input"])
        row1.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            row1, text="MODEL", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_dim"], width=8, anchor="w",
        ).pack(side=tk.LEFT)

        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            row1, textvariable=self.model_var, state="readonly",
            width=36, font=(FONT_FAMILY, 10, "bold"),
            style="Dark.TCombobox", height=COMBOBOX_DROPDOWN_HEIGHT,
        )
        self.model_combo.pack(side=tk.LEFT, padx=(5, 10))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_changed)

        info_frame = tk.Frame(row1, bg=COLORS["bg_input"])
        info_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.duration_label = tk.Label(
            info_frame, text="10s duration", font=(FONT_FAMILY, 10),
            bg=COLORS["bg_input"], fg=COLORS["text_dim"],
        )
        self.duration_label.pack(side=tk.TOP, anchor="w")

        # ⓘ info icon — hover to see model notes (blue = has notes, dim = none)
        self.model_info_icon = tk.Label(
            info_frame, text="ⓘ info",
            font=(FONT_FAMILY, 8), cursor="question_arrow",
            bg=COLORS["bg_input"], fg=COLORS["text_dim"],
        )
        self.model_info_icon.pack(side=tk.TOP, anchor="w")
        HoverTooltip(self.model_info_icon, self._get_current_model_notes)

        # Row 2: Output mode
        row2 = tk.Frame(left_col, bg=COLORS["bg_input"])
        row2.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            row2, text="OUTPUT", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_dim"], width=8, anchor="w",
        ).pack(side=tk.LEFT)

        self.output_mode_var = tk.StringVar(value="source")
        self.source_radio = tk.Radiobutton(
            row2, text="Same as Source", variable=self.output_mode_var, value="source",
            font=(FONT_FAMILY, 10), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_output_mode_changed,
        )
        self.source_radio.pack(side=tk.LEFT, padx=(5, 10))

        self.custom_radio = tk.Radiobutton(
            row2, text="Custom Folder:", variable=self.output_mode_var, value="custom",
            font=(FONT_FAMILY, 10), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_output_mode_changed,
        )
        self.custom_radio.pack(side=tk.LEFT)

        self.output_path_var = tk.StringVar()
        self.output_entry = tk.Entry(
            row2, textvariable=self.output_path_var, font=(FONT_FAMILY, 10),
            bg=COLORS["bg_input"], fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            disabledbackground=COLORS["bg_input"], disabledforeground=COLORS["text_dim"],
            width=16, borderwidth=0, highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self.output_entry.pack(side=tk.LEFT, padx=8, pady=2, fill=tk.Y)

        self.browse_btn = tk.Button(
            row2, text="BROWSE", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["text_light"],
            padx=10, relief=tk.FLAT, borderwidth=0, command=self._browse_output_folder,
        )
        self.browse_btn.pack(side=tk.LEFT, padx=2)

        # Separator (between model/output rows and option rows)
        ttk.Separator(left_col, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(2, 10))

        lbl_w = 10  # consistent label width in chars

        # Options: Loop Video
        rA = tk.Frame(left_col, bg=COLORS["bg_input"])
        rA.pack(fill=tk.X, pady=(0, 4))
        tk.Label(rA, text="Options:", font=(FONT_FAMILY, 10),
                 bg=COLORS["bg_input"], fg=COLORS["text_light"],
                 width=lbl_w, anchor="w").pack(side=tk.LEFT)
        self.loop_video_var = tk.BooleanVar(value=False)
        self.loop_checkbox = tk.Checkbutton(
            rA, text="Loop Video (ping-pong)", variable=self.loop_video_var,
            font=(FONT_FAMILY, 10), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_loop_changed,
        )
        self.loop_checkbox.pack(side=tk.LEFT)
        self.loop_info_label = tk.Label(
            rA, text="(requires FFmpeg)", font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"], fg=COLORS["text_dim"],
        )
        self.loop_info_label.pack(side=tk.LEFT, padx=4)

        # Allow reprocessing
        rB = tk.Frame(left_col, bg=COLORS["bg_input"])
        rB.pack(fill=tk.X, pady=(0, 4))
        tk.Label(rB, text="", font=(FONT_FAMILY, 10),
                 bg=COLORS["bg_input"], width=lbl_w).pack(side=tk.LEFT)
        self.reprocess_var = tk.BooleanVar(value=False)
        self.reprocess_checkbox = tk.Checkbutton(
            rB, text="Allow reprocessing", variable=self.reprocess_var,
            font=(FONT_FAMILY, 10), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_reprocess_changed,
        )
        self.reprocess_checkbox.pack(side=tk.LEFT)
        self.reprocess_mode_frame = tk.Frame(rB, bg=COLORS["bg_input"])
        self.reprocess_mode_frame.pack(side=tk.LEFT, padx=(8, 0))
        self.reprocess_mode_var = tk.StringVar(value="increment")
        self.overwrite_radio = tk.Radiobutton(
            self.reprocess_mode_frame, text="Overwrite",
            variable=self.reprocess_mode_var, value="overwrite",
            font=(FONT_FAMILY, 9), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_reprocess_mode_changed,
        )
        self.overwrite_radio.pack(side=tk.LEFT, padx=2)
        self.increment_radio = tk.Radiobutton(
            self.reprocess_mode_frame, text="Increment (_2, _3\u2026)",
            variable=self.reprocess_mode_var, value="increment",
            font=(FONT_FAMILY, 9), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_reprocess_mode_changed,
        )
        self.increment_radio.pack(side=tk.LEFT, padx=2)
        self._update_reprocess_mode_visibility()

        # Logging
        rC = tk.Frame(left_col, bg=COLORS["bg_input"])
        rC.pack(fill=tk.X, pady=(0, 4))
        tk.Label(rC, text="Logging:", font=(FONT_FAMILY, 10),
                 bg=COLORS["bg_input"], fg=COLORS["text_light"],
                 width=lbl_w, anchor="w").pack(side=tk.LEFT)
        self.verbose_gui_var = tk.BooleanVar(value=False)
        self.verbose_checkbox = tk.Checkbutton(
            rC, text="Verbose Mode", variable=self.verbose_gui_var,
            font=(FONT_FAMILY, 10), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_verbose_changed,
        )
        self.verbose_checkbox.pack(side=tk.LEFT)
        self.verbose_info_label = tk.Label(
            rC, text="(detailed processing log)", font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"], fg=COLORS["text_dim"],
        )
        self.verbose_info_label.pack(side=tk.LEFT, padx=4)

        # File Filter — replaces the old "Folder:" row with clearer labeling
        rD = tk.Frame(left_col, bg=COLORS["bg_input"])
        rD.pack(fill=tk.X, pady=(0, 2))
        tk.Label(rD, text="Filter:", font=(FONT_FAMILY, 10),
                 bg=COLORS["bg_input"], fg=COLORS["text_light"],
                 width=lbl_w, anchor="w").pack(side=tk.LEFT)
        self.folder_pattern_var = tk.StringVar(value="")
        self.folder_pattern_entry = tk.Entry(
            rD, textvariable=self.folder_pattern_var, font=(FONT_FAMILY, 10),
            bg=COLORS["bg_main"], fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"], width=16,
            borderwidth=0, highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self.folder_pattern_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.folder_pattern_entry.bind("<FocusOut>", self._on_folder_pattern_changed)
        self.folder_pattern_entry.bind("<Return>", self._on_folder_pattern_changed)
        tk.Label(rD, text="Match:", font=(FONT_FAMILY, 9),
                 bg=COLORS["bg_input"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=(0, 4))
        self.folder_match_mode_var = tk.StringVar(value="partial")
        self.partial_radio = tk.Radiobutton(
            rD, text="Partial", variable=self.folder_match_mode_var, value="partial",
            font=(FONT_FAMILY, 9), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_folder_match_mode_changed,
        )
        self.partial_radio.pack(side=tk.LEFT, padx=2)
        self.exact_radio = tk.Radiobutton(
            rD, text="Exact", variable=self.folder_match_mode_var, value="exact",
            font=(FONT_FAMILY, 9), bg=COLORS["bg_input"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"], command=self._on_folder_match_mode_changed,
        )
        self.exact_radio.pack(side=tk.LEFT, padx=2)
        # Filter help text — explains what Folder/Match do
        rD2 = tk.Frame(left_col, bg=COLORS["bg_input"])
        rD2.pack(fill=tk.X, pady=(0, 6))
        tk.Label(rD2, text="", bg=COLORS["bg_input"], width=lbl_w).pack(side=tk.LEFT)
        tk.Label(
            rD2,
            text="Subfolder name to match when processing a folder (blank \u2192 all files)"
                 " \u00b7 Partial: name contains filter \u00b7 Exact: name equals filter",
            font=(FONT_FAMILY, 8), bg=COLORS["bg_input"], fg=COLORS["text_dim"],
            wraplength=280, justify="left",
        ).pack(side=tk.LEFT)

        # Video settings
        rE = tk.Frame(left_col, bg=COLORS["bg_input"])
        rE.pack(fill=tk.X, pady=(0, 4))
        tk.Label(rE, text="Video:", font=(FONT_FAMILY, 10),
                 bg=COLORS["bg_input"], fg=COLORS["text_light"],
                 width=lbl_w, anchor="w").pack(side=tk.LEFT)
        tk.Label(rE, text="Aspect:", font=(FONT_FAMILY, 9),
                 bg=COLORS["bg_input"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=(0, 3))
        self.aspect_ratio_var = tk.StringVar(value="9:16")
        self.aspect_ratio_combo = ttk.Combobox(
            rE, textvariable=self.aspect_ratio_var,
            values=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
            state="readonly", width=6, font=(FONT_FAMILY, 9), style="Dark.TCombobox",
        )
        self.aspect_ratio_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.aspect_ratio_combo.bind("<<ComboboxSelected>>", self._on_aspect_ratio_changed)
        tk.Label(rE, text="Duration:", font=(FONT_FAMILY, 9),
                 bg=COLORS["bg_input"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=(0, 3))
        self.duration_var = tk.StringVar(value="10s")
        self.duration_combo = ttk.Combobox(
            rE, textvariable=self.duration_var, values=["5s", "10s"],
            state="readonly", width=5, font=(FONT_FAMILY, 9), style="Dark.TCombobox",
        )
        self.duration_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.duration_combo.bind("<<ComboboxSelected>>", self._on_duration_changed)
        tk.Label(rE, text="Res:", font=(FONT_FAMILY, 9),
                 bg=COLORS["bg_input"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=(0, 3))
        self.resolution_var = tk.StringVar(value="720p")
        self.resolution_combo = ttk.Combobox(
            rE, textvariable=self.resolution_var, values=["480p", "720p"],
            state="readonly", width=5, font=(FONT_FAMILY, 9), style="Dark.TCombobox",
        )
        self.resolution_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.resolution_combo.bind("<<ComboboxSelected>>", self._on_resolution_changed)
        self.schema_diagnostic_label = tk.Label(
            rE, text="", font=(FONT_FAMILY, 9), bg=COLORS["bg_input"], fg=COLORS["text_dim"],
        )
        self.schema_diagnostic_label.pack(side=tk.LEFT, padx=2)
        self.video_settings_info = tk.Label(
            rE, text="(model-dependent)", font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"], fg=COLORS["text_dim"],
        )
        self.video_settings_info.pack(side=tk.LEFT, padx=2)

        # Seed & misc options
        rF = tk.Frame(left_col, bg=COLORS["bg_input"])
        rF.pack(fill=tk.X, pady=(0, 4))
        tk.Label(rF, text="Options:", font=(FONT_FAMILY, 10),
                 bg=COLORS["bg_input"], fg=COLORS["text_light"],
                 width=lbl_w, anchor="w").pack(side=tk.LEFT)
        tk.Label(rF, text="Seed:", font=(FONT_FAMILY, 9),
                 bg=COLORS["bg_input"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=(0, 3))
        self.seed_var = tk.StringVar(value="-1")
        self.seed_entry = tk.Entry(
            rF, textvariable=self.seed_var, font=(FONT_FAMILY, 10),
            bg=COLORS["bg_main"], fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"], width=10,
            borderwidth=0, highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self.seed_entry.pack(side=tk.LEFT, padx=(0, 3))
        self.seed_entry.bind("<FocusOut>", self._on_seed_changed)
        self.seed_entry.bind("<Return>", self._on_seed_changed)
        self.random_seed_var = tk.BooleanVar(value=True)
        self.random_seed_checkbox = tk.Checkbutton(
            rF, text="Random", variable=self.random_seed_var, font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"], fg=COLORS["text_light"], selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"], activeforeground=COLORS["text_light"],
            command=self._on_random_seed_changed,
        )
        self.random_seed_checkbox.pack(side=tk.LEFT, padx=(0, 12))
        self.camera_fixed_var = tk.BooleanVar(value=False)
        self.camera_fixed_checkbox = tk.Checkbutton(
            rF, text="Camera Fixed", variable=self.camera_fixed_var, font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"], fg=COLORS["text_light"], selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"], activeforeground=COLORS["text_light"],
            command=self._on_camera_fixed_changed,
        )
        self.camera_fixed_checkbox.pack(side=tk.LEFT, padx=(0, 12))
        self.generate_audio_var = tk.BooleanVar(value=False)
        self.generate_audio_checkbox = tk.Checkbutton(
            rF, text="Generate Audio", variable=self.generate_audio_var, font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"], fg=COLORS["text_light"], selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"], activeforeground=COLORS["text_light"],
            command=self._on_generate_audio_changed,
        )
        self.generate_audio_checkbox.pack(side=tk.LEFT)
        self._update_seed_entry_state()

        # ── RIGHT COLUMN: built inline or externally via build_prompt_panel() ──
        if self._build_prompt_inline:
            self.build_prompt_panel(body_frame)

    def build_prompt_panel(self, parent: tk.Widget) -> tk.Frame:
        """Build the prompt editor UI into `parent`.

        Called automatically during _setup_ui (default) when build_prompt=True,
        or externally by main_window.py for side-by-side drop zone + prompt layout.
        """
        right_col = tk.Frame(
            parent, bg=COLORS["bg_panel"],
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.prompt_preview_container = right_col  # compatibility reference

        right_inner = tk.Frame(right_col, bg=COLORS["bg_panel"], padx=8, pady=6)
        right_inner.pack(fill=tk.BOTH, expand=True)

        # Slot selector bar — 1 through 10 in a single inline row
        slot_bar = tk.Frame(right_inner, bg=COLORS["bg_panel"])
        slot_bar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(slot_bar, text="SLOT", font=(FONT_FAMILY, 9, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(side=tk.LEFT, padx=(0, 8))
        self.slot_var = tk.IntVar(value=1)
        self._slot_buttons = []
        for i in range(1, 11):
            rb = tk.Radiobutton(
                slot_bar, text=str(i), variable=self.slot_var, value=i,
                font=(FONT_FAMILY, 10, "bold"),
                bg=COLORS["bg_panel"], fg=COLORS["text_light"],
                selectcolor=COLORS["accent_blue"],
                activebackground=COLORS["bg_panel"], activeforeground=COLORS["accent_blue"],
                indicatoron=False, width=2, relief=tk.FLAT,
                command=self._on_slot_changed,
            )
            rb.pack(side=tk.LEFT, padx=1)
            self._slot_buttons.append(rb)

        # Title row (read-only by default; Edit mode enables it)
        title_row = tk.Frame(right_inner, bg=COLORS["bg_panel"])
        title_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(title_row, text="Title:", font=(FONT_FAMILY, 10, "bold"),
                 bg=COLORS["bg_panel"], fg=COLORS["text_dim"]).pack(side=tk.LEFT)
        self.prompt_title_var = tk.StringVar()
        self.prompt_title_entry = tk.Entry(
            title_row, textvariable=self.prompt_title_var,
            font=(FONT_FAMILY, 10), bg=COLORS["bg_main"], fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"], relief=tk.FLAT,
            highlightthickness=1, highlightbackground=COLORS["border"],
            state="disabled", disabledforeground=COLORS["text_dim"],
            disabledbackground=COLORS["bg_main"],
        )
        self.prompt_title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        # Prompt text area — scrollbar packed first so it claims its rightmost space
        text_frame = tk.Frame(right_inner, bg=COLORS["bg_panel"])
        text_frame.pack(fill=tk.BOTH, expand=True)
        self.prompt_preview = tk.Text(
            text_frame, font=(FONT_FAMILY, 10),
            bg=COLORS["bg_main"], fg=COLORS["text_dim"],
            height=15, wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
            insertbackground=COLORS["text_light"], state="disabled",
        )
        preview_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.prompt_preview.yview)
        self.prompt_preview.configure(yscrollcommand=preview_scroll.set)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)  # scrollbar first
        self.prompt_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.prompt_preview.bind("<KeyRelease>", self._update_prompt_char_count)

        # Footer: char count badge + Edit button + Save button
        prompt_footer = tk.Frame(right_inner, bg=COLORS["bg_panel"])
        prompt_footer.pack(fill=tk.X, pady=(6, 0))
        char_badge = tk.Frame(
            prompt_footer, bg=COLORS["bg_input"],
            highlightthickness=1, highlightbackground=COLORS["border"],
            padx=6, pady=2,
        )
        char_badge.pack(side=tk.LEFT)
        self.prompt_char_count_label = tk.Label(
            char_badge, text="0 chars", font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"], fg=COLORS["text_dim"],
        )
        self.prompt_char_count_label.pack()
        self.edit_prompt_btn = tk.Button(
            prompt_footer, text="Edit", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_light"],
            activebackground=COLORS["bg_main"], activeforeground=COLORS["text_light"],
            padx=10, pady=2, relief=tk.FLAT, borderwidth=0,
            command=self._enter_edit_mode,
        )
        self.edit_prompt_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self.save_prompt_btn = tk.Button(
            prompt_footer, text="Save Prompt", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_light"],
            activebackground=COLORS["bg_main"], activeforeground=COLORS["text_light"],
            padx=10, pady=2, relief=tk.FLAT, borderwidth=0,
            state="disabled", command=self._save_prompt,
        )
        self.save_prompt_btn.pack(side=tk.RIGHT)

        # Load prompt config now that widgets exist
        self._load_prompt_config()
        return right_col

    def _load_prompt_config(self):
        """Load prompt slot/title/text. Safe to call before build_prompt_panel() — returns early."""
        if not hasattr(self, "slot_var"):
            return
        self.slot_var.set(self.config.get("current_prompt_slot", 1))
        self._update_prompt_preview()
        self._update_slot_button_colors()

    def _update_slot_button_colors(self):
        """Set selected slot button to black text on blue; others to light text on dark."""
        if not hasattr(self, "_slot_buttons"):
            return
        current = self.slot_var.get()
        for i, rb in enumerate(self._slot_buttons, 1):
            if i == current:
                rb.config(fg="#111111", bg=COLORS["accent_blue"])
            else:
                rb.config(fg=COLORS["text_light"], bg=COLORS["bg_panel"])

    def _load_config(self):
        """Load configuration values into UI."""
        # Model list + inline model selector
        self.models = ModelFetcher.get_cached_or_fallback(self.config)
        if not self.models:
            self.models = [
                {
                    "name": self.config.get("model_display_name", "Kling 2.5 Turbo Pro"),
                    "endpoint": self.config.get("current_model", ""),
                    "duration_default": self.config.get("video_duration", 10),
                }
            ]

        model_names = [get_model_display_name(m) for m in self.models]
        self.model_combo["values"] = model_names

        current_model = self.config.get("current_model", "")
        selected_index = 0
        for i, model in enumerate(self.models):
            if model.get("endpoint") == current_model:
                selected_index = i
                break
        else:
            current_name = self.config.get("model_display_name", "")
            if current_name in model_names:
                selected_index = model_names.index(current_name)

        if model_names:
            self.model_combo.current(selected_index)
            self.model_var.set(model_names[selected_index])
            self._update_model_info_icon()

        # Output mode
        if self.config.get("use_source_folder", True):
            self.output_mode_var.set("source")
        else:
            self.output_mode_var.set("custom")
        self.output_path_var.set(self.config.get("output_folder", ""))
        self._update_output_entry_state()

        # Prompt slot/editor (deferred if prompt panel not yet built externally)
        self._load_prompt_config()

        # Duration
        duration = self.config.get("video_duration", 10)
        self.duration_var.set(f"{duration}s")
        if hasattr(self, 'duration_label'):
            self.duration_label.config(text=f"{duration}s duration")
        logger.debug(f"Loaded duration: {duration}s")

        # Loop video option
        self.loop_video_var.set(self.config.get("loop_videos", False))
        self._check_ffmpeg_status()

        # Reprocess options
        self.reprocess_var.set(self.config.get("allow_reprocess", False))
        self.reprocess_mode_var.set(self.config.get("reprocess_mode", "increment"))
        self._update_reprocess_mode_visibility()

        # Verbose GUI mode
        self.verbose_gui_var.set(self.config.get("verbose_gui_mode", False))

        # Folder filter options
        self.folder_pattern_var.set(self.config.get("folder_filter_pattern", ""))
        self.folder_match_mode_var.set(self.config.get("folder_match_mode", "partial"))

        # Advanced video settings
        self.aspect_ratio_var.set(self.config.get("aspect_ratio", "9:16"))
        self.resolution_var.set(self.config.get("resolution", "720p"))

        # Seed settings
        seed = self.config.get("seed", -1)
        self.seed_var.set(str(seed))
        self.random_seed_var.set(seed == -1)
        self._update_seed_entry_state()

        # Additional options
        self.camera_fixed_var.set(self.config.get("camera_fixed", False))
        self.generate_audio_var.set(self.config.get("generate_audio", False))

        # Update parameter visibility based on current model
        current_model = self.config.get(
            "current_model", "fal-ai/kling-video/v2.1/pro/image-to-video"
        )
        self.update_parameter_visibility(current_model)

    def _on_model_changed(self, event=None):
        """Handle inline model selection changes."""
        selected_name = self.model_var.get()
        if not selected_name:
            return

        selected_model = None
        selected_index = self.model_combo.current()
        if 0 <= selected_index < len(self.models):
            selected_model = self.models[selected_index]
        else:
            for model in self.models:
                if model.get("name") == selected_name:
                    selected_model = model
                    break

        if not selected_model:
            return

        model_endpoint = selected_model.get("endpoint", "")
        if not model_endpoint:
            return

        self.config["current_model"] = model_endpoint
        self.config["model_display_name"] = selected_model.get("name", selected_name)

        self.update_parameter_visibility(model_endpoint)

        duration_text = self.duration_var.get().rstrip("s").strip()
        if duration_text.isdigit():
            self.config["video_duration"] = int(duration_text)
            self.duration_label.config(text=f"{duration_text}s duration")

        self._update_model_info_icon(selected_model)
        self._notify_change(f"Model changed to {self.config['model_display_name']}")

    def _get_current_model_notes(self) -> str:
        """Return the notes string for the currently selected model (used by HoverTooltip)."""
        idx = self.model_combo.current()
        if hasattr(self, "models") and 0 <= idx < len(self.models):
            return self.models[idx].get("notes", "")
        return ""

    def _update_model_info_icon(self, model: dict = None):
        """Set info icon color: blue when model has notes, dim otherwise."""
        if not hasattr(self, "model_info_icon"):
            return
        if model is None:
            idx = self.model_combo.current()
            model = self.models[idx] if hasattr(self, "models") and 0 <= idx < len(self.models) else {}
        has_notes = bool(model.get("notes", ""))
        self.model_info_icon.config(
            fg=COLORS["accent_blue"] if has_notes else COLORS["text_dim"]
        )

    def _check_ffmpeg_status(self):
        """Check if FFmpeg is available and update UI."""
        try:
            from .video_looper import check_ffmpeg_available

            available, message = check_ffmpeg_available()
            if available:
                self.loop_info_label.config(text="(FFmpeg ready)", fg="#64FF64")
            else:
                self.loop_info_label.config(text="(FFmpeg not found)", fg="#FF6464")
        except Exception:
            self.loop_info_label.config(text="(requires FFmpeg)", fg=COLORS["text_dim"])

    def _on_loop_changed(self):
        """Handle loop video checkbox change."""
        self.config["loop_videos"] = self.loop_video_var.get()
        status = "enabled" if self.loop_video_var.get() else "disabled"
        self._notify_change(f"Loop video {status}")

    def _on_reprocess_changed(self):
        """Handle reprocess checkbox change."""
        self.config["allow_reprocess"] = self.reprocess_var.get()
        self._update_reprocess_mode_visibility()
        status = "enabled" if self.reprocess_var.get() else "disabled"
        self._notify_change(f"Reprocessing {status}")

    def _on_reprocess_mode_changed(self):
        """Handle reprocess mode radio change."""
        mode = self.reprocess_mode_var.get()
        self.config["reprocess_mode"] = mode
        self._notify_change(f"Reprocess mode set to {mode}")

    def _on_verbose_changed(self):
        """Handle verbose mode checkbox change."""
        self.config["verbose_gui_mode"] = self.verbose_gui_var.get()
        status = "enabled" if self.verbose_gui_var.get() else "disabled"
        self._notify_change(f"Verbose mode {status}")

    def _on_folder_pattern_changed(self, event=None):
        """Handle folder pattern entry change."""
        pattern = self.folder_pattern_var.get().strip()
        self.config["folder_filter_pattern"] = pattern
        if pattern:
            self._notify_change(f"Folder pattern set to '{pattern}'")
        else:
            self._notify_change("Folder pattern cleared")

    def _on_folder_match_mode_changed(self):
        """Handle folder match mode radio change."""
        mode = self.folder_match_mode_var.get()
        self.config["folder_match_mode"] = mode
        self._notify_change(f"Folder match mode set to {mode}")

    def _on_aspect_ratio_changed(self, event=None):
        """Handle aspect ratio combobox change."""
        ratio = self.aspect_ratio_var.get()
        self.config["aspect_ratio"] = ratio
        self._notify_change(f"Aspect ratio set to {ratio}")

    def _on_resolution_changed(self, event=None):
        """Handle resolution combobox change."""
        resolution = self.resolution_var.get()
        self.config["resolution"] = resolution
        self._notify_change(f"Resolution set to {resolution}")

    def _on_duration_changed(self, event=None):
        """Handle duration selection change with validation."""
        try:
            # Extract numeric value from "10s" format
            duration_str = self.duration_var.get().rstrip('s').strip()
            if not duration_str.isdigit():
                logger.error(f"Invalid duration format: {self.duration_var.get()}")
                return
            
            duration = int(duration_str)
            
            # Validate duration is positive
            if duration <= 0:
                logger.error(f"Duration must be positive, got: {duration}")
                return

            # Update config
            self.config["video_duration"] = duration

            # Update display label if it exists
            if hasattr(self, 'duration_label'):
                self.duration_label.config(text=f"{duration}s duration")

            # Notify parent window of change
            self._notify_change(f"Duration set to {duration}s")

            logger.debug(f"Duration changed to: {duration}s")

        except (ValueError, AttributeError) as e:
            logger.error(f"Error changing duration: {e}")
            # Revert to previous valid value
            current_duration = self.config.get("video_duration", 10)
            self.duration_var.set(f"{current_duration}s")

    def _on_seed_changed(self, event=None):
        """Handle seed entry change."""
        try:
            seed_str = self.seed_var.get().strip()
            seed = int(seed_str) if seed_str else -1
            self.config["seed"] = seed
            # Update random checkbox to reflect current state
            self.random_seed_var.set(seed == -1)
            self._notify_change(
                f"Seed set to {seed}" if seed != -1 else "Seed set to random"
            )
        except ValueError:
            # Invalid input, reset to -1
            self.seed_var.set("-1")
            self.config["seed"] = -1
            self.random_seed_var.set(True)
            self._notify_change("Invalid seed, reset to random")

    def _on_random_seed_changed(self):
        """Handle random seed checkbox change."""
        if self.random_seed_var.get():
            self.seed_var.set("-1")
            self.config["seed"] = -1
            self._notify_change("Seed set to random")
        else:
            # If unchecking random, set a default seed value
            self.seed_var.set("42")
            self.config["seed"] = 42
            self._notify_change("Seed set to 42 (editable)")
        self._update_seed_entry_state()

    def _update_seed_entry_state(self):
        """Enable/disable seed entry based on random checkbox."""
        if self.random_seed_var.get():
            self.seed_entry.config(state="disabled")
        else:
            self.seed_entry.config(state="normal")

    def _on_camera_fixed_changed(self):
        """Handle camera fixed checkbox change."""
        self.config["camera_fixed"] = self.camera_fixed_var.get()
        status = "enabled" if self.camera_fixed_var.get() else "disabled"
        self._notify_change(f"Camera fixed {status}")

    def _on_generate_audio_changed(self):
        """Handle generate audio checkbox change."""
        self.config["generate_audio"] = self.generate_audio_var.get()
        status = "enabled" if self.generate_audio_var.get() else "disabled"
        self._notify_change(f"Generate audio {status}")

    def _update_reprocess_mode_visibility(self):
        """Show/hide reprocess mode options based on checkbox."""
        if self.reprocess_var.get():
            self.overwrite_radio.config(state="normal")
            self.increment_radio.config(state="normal")
        else:
            self.overwrite_radio.config(state="disabled")
            self.increment_radio.config(state="disabled")

    def _on_output_mode_changed(self):
        """Handle output mode radio change."""
        is_source = self.output_mode_var.get() == "source"
        self.config["use_source_folder"] = is_source
        self._update_output_entry_state()
        mode_desc = "source folder" if is_source else "custom folder"
        self._notify_change(f"Output mode set to {mode_desc}")

    def _update_output_entry_state(self):
        """Enable/disable output path entry based on mode."""
        if self.output_mode_var.get() == "source":
            self.output_entry.config(state="disabled")
            self.browse_btn.config(state="disabled")
        else:
            self.output_entry.config(state="normal")
            self.browse_btn.config(state="normal")

    def _browse_output_folder(self):
        """Open folder browser for output path."""
        folder = filedialog.askdirectory(
            title="Select Output Folder", initialdir=self.output_path_var.get() or "."
        )
        if folder:
            self.output_path_var.set(folder)
            self.config["output_folder"] = folder
            self._notify_change(f"Output folder set to {folder}")

    def _on_slot_changed(self):
        """Handle prompt slot change — discard any unsaved edits first."""
        if self._prompt_edit_mode:
            self._exit_edit_mode_internal()
        slot = self.slot_var.get()
        self.config["current_prompt_slot"] = slot
        self._update_prompt_preview()
        self._update_slot_button_colors()
        self._notify_change(f"Prompt slot changed to {slot}")

    def _update_prompt_preview(self):
        """Load selected slot title/prompt into the read-only display widgets."""
        slot = self.slot_var.get()
        saved_prompts = self.config.setdefault("saved_prompts", {})
        saved_titles = self.config.setdefault("prompt_titles", {})
        prompt = saved_prompts.get(str(slot), "") or ""
        title = saved_titles.get(str(slot), "") or ""

        # Title entry: briefly enable to update, then restore disabled state
        self.prompt_title_entry.config(state="normal")
        self.prompt_title_var.set(title)
        if not self._prompt_edit_mode:
            self.prompt_title_entry.config(state="disabled")

        # Text widget: briefly enable to update, then restore disabled state
        self.prompt_preview.config(state="normal")
        self.prompt_preview.delete("1.0", tk.END)
        self.prompt_preview.insert("1.0", prompt)
        if not self._prompt_edit_mode:
            self.prompt_preview.config(state="disabled")

        self._update_prompt_char_count()

    def _update_prompt_char_count(self, event=None):
        """Update live prompt character count."""
        prompt_text = self.prompt_preview.get("1.0", "end-1c")
        self.prompt_char_count_label.config(text=f"{len(prompt_text)} chars")

    def _save_prompt(self):
        """Persist title and prompt text for the currently selected slot."""
        slot = str(self.slot_var.get())
        saved_prompts = self.config.setdefault("saved_prompts", {})
        saved_titles = self.config.setdefault("prompt_titles", {})

        saved_prompts[slot] = self.prompt_preview.get("1.0", "end-1c")
        saved_titles[slot] = self.prompt_title_var.get().strip()

        self.config["saved_prompts"] = saved_prompts
        self.config["prompt_titles"] = saved_titles
        self._update_prompt_char_count()
        self._exit_edit_mode_internal()  # widgets already saved above
        self._notify_change(f"Saved prompt slot {slot}")

    def _notify_change(self, description: Optional[str] = None):
        """Notify that config has changed."""
        if self.on_config_changed:
            self.on_config_changed(self.config, description)

    def _enter_edit_mode(self):
        """Switch prompt editor to editable mode."""
        self._prompt_edit_mode = True
        self.prompt_title_entry.config(state="normal")
        self.prompt_preview.config(state="normal", fg=COLORS["text_light"])
        self.save_prompt_btn.config(state="normal")
        self.edit_prompt_btn.config(text="Cancel", command=self._cancel_edit)

    def _cancel_edit(self):
        """Discard edits and return to read-only mode."""
        self._exit_edit_mode_internal()
        # Reload the saved content to discard in-progress changes
        self._update_prompt_preview()

    def _exit_edit_mode_internal(self):
        """Return prompt editor to read-only mode."""
        self._prompt_edit_mode = False
        self.prompt_title_entry.config(state="disabled")
        self.prompt_preview.config(state="disabled", fg=COLORS["text_dim"])
        self.save_prompt_btn.config(state="disabled")
        self.edit_prompt_btn.config(text="Edit", command=self._enter_edit_mode)

    def _position_prompt_preview(self):
        """No-op — prompt editor is now in the right column (pack layout)."""
        pass

    def apply_ui_config(self, ui_config: dict):
        """Apply UI layout configuration to config panel widgets."""
        if not ui_config:
            return
        self._ui_config = ui_config
        config_panel = ui_config.get("config_panel", {})
        try:
            preview_height = int(config_panel.get("prompt_preview_height", 6))
            preview_font_size = int(config_panel.get("prompt_preview_font_size", 9))
        except (TypeError, ValueError):
            return
        if hasattr(self, "prompt_preview"):
            self.prompt_preview.config(
                height=max(4, preview_height),
                font=(FONT_FAMILY, max(6, preview_font_size)),
            )

    def get_config(self) -> dict:
        """Get current configuration."""
        return self.config.copy()

    def cleanup(self):
        """Clean up tkinter variables to prevent thread-related errors on exit.

        This must be called before the root window is destroyed to avoid
        'main thread is not in main loop' errors on Python 3.14+.
        """
        # List all tkinter variable attributes to clean up
        var_attrs = [
            "output_mode_var",
            "output_path_var",
            "model_var",
            "slot_var",
            "prompt_title_var",
            "loop_video_var",
            "reprocess_var",
            "reprocess_mode_var",
            "verbose_gui_var",
            "folder_pattern_var",
            "folder_match_mode_var",
            "duration_var",
            "aspect_ratio_var",
            "resolution_var",
            "seed_var",
            "random_seed_var",
            "camera_fixed_var",
            "generate_audio_var",
        ]
        for attr in var_attrs:
            if hasattr(self, attr):
                try:
                    delattr(self, attr)
                except Exception:
                    pass

    def update_parameter_visibility(self, model_endpoint: str):
        """Update visibility of parameter controls based on model capabilities.

        Uses ModelSchemaManager to determine which parameters the selected model
        supports. Controls for unsupported parameters are visually disabled with
        grayed-out styling to indicate they won't be sent to the API.

        Args:
            model_endpoint: The fal.ai model endpoint (e.g., "fal-ai/kling-video/v2.5/pro/image-to-video")
        """
        # Map UI controls to their corresponding API parameter names
        # Format: param_name -> (controls_tuple, associated_labels_tuple)
        param_controls = {
            "seed": (
                (self.seed_entry, self.random_seed_checkbox),
                (),  # No additional labels - "Seed:" label is always visible
            ),
            "aspect_ratio": (
                (self.aspect_ratio_combo,),
                (),  # "Aspect:" label handled separately in row
            ),
            "resolution": (
                (self.resolution_combo,),
                (),  # "Resolution:" label handled separately in row
            ),
            "camera_fixed": ((self.camera_fixed_checkbox,), ()),
            "generate_audio": ((self.generate_audio_checkbox,), ()),
        }

        try:
            from model_schema_manager import ModelSchemaManager

            api_key = os.getenv("FAL_KEY") or self.config.get("falai_api_key", "")
            if not api_key:
                logger.warning("No API key available for schema lookup")
                # Apply conservative default: enable all controls with unknown status
                param_controls = {
                    "seed": ((self.seed_entry, self.random_seed_checkbox), ()),
                    "aspect_ratio": ((self.aspect_ratio_combo,), ()),
                    "resolution": ((self.resolution_combo,), ()),
                    "camera_fixed": ((self.camera_fixed_checkbox,), ()),
                    "generate_audio": ((self.generate_audio_checkbox,), ()),
                }

                for param_name, (controls, labels) in param_controls.items():
                    for control in controls:
                        if control is None:
                            continue
                        try:
                            if isinstance(control, ttk.Combobox):
                                control.config(state="readonly")
                            elif isinstance(control, tk.Entry):
                                control.config(state="normal")
                            elif isinstance(control, tk.Checkbutton):
                                control.config(state="normal")
                        except tk.TclError as e:
                            logger.debug(f"Could not reset {param_name} control: {e}")

                # Update info label
                if (
                    hasattr(self, "video_settings_info")
                    and self.video_settings_info is not None
                ):
                    try:
                        self.video_settings_info.config(
                            text="(model-dependent)",
                            fg=COLORS["text_dim"],
                        )
                    except tk.TclError as e:
                        logger.debug(f"Could not update video_settings_info: {e}")
                return

            schema_manager = ModelSchemaManager(api_key)

            # Get all supported parameters for this model (defensive handling)
            supported_params = set(
                schema_manager.get_supported_parameters(model_endpoint) or []
            )

            # Visual styling for supported vs unsupported
            SUPPORTED_FG = COLORS["text_light"]
            UNSUPPORTED_FG = COLORS["text_unsupported"]
            SUPPORTED_BG = COLORS["bg_main"]
            UNSUPPORTED_BG = COLORS["bg_unsupported"]

            # Get duration options from schema
            duration_param = schema_manager.get_parameter_info(model_endpoint, "duration")
            if duration_param and hasattr(duration_param, 'enum') and duration_param.enum:
                # Model specifies exact allowed durations
                duration_values = [f"{int(d)}s" for d in duration_param.enum]
                logger.debug(f"Model {model_endpoint} supports durations: {duration_values}")
            else:
                # Fallback: use model_metadata.py duration_options
                from model_metadata import get_duration_options
                duration_secs = get_duration_options(model_endpoint)
                duration_values = [f"{d}s" for d in duration_secs]
                logger.debug(f"Using metadata durations for {model_endpoint}: {duration_values}")

            # Update duration dropdown with model-specific values
            if hasattr(self, 'duration_combo') and self.duration_combo is not None:
                try:
                    current_value = self.duration_var.get()
                    self.duration_combo.config(values=duration_values)

                    # Preserve selection if valid, else reset to first option
                    if current_value not in duration_values:
                        new_default = duration_values[0] if duration_values else "10s"
                        self.duration_var.set(new_default)
                        logger.info(f"Duration reset to {new_default} (was {current_value})")
                except tk.TclError as e:
                    logger.debug(f"Could not update duration dropdown: {e}")

            for param_name, (controls, labels) in param_controls.items():
                supported = param_name in supported_params
                state = "normal" if supported else "disabled"
                fg_color = SUPPORTED_FG if supported else UNSUPPORTED_FG
                bg_color = SUPPORTED_BG if supported else UNSUPPORTED_BG

                for control in controls:
                    if control is None:
                        continue
                    try:
                        # Handle different widget types
                        if isinstance(control, ttk.Combobox):
                            # Always readonly (clickable) but visually dimmed when unsupported
                            control.config(state="readonly")

                            # Apply visual feedback via foreground color
                            # Note: ttk.Combobox styling is limited, but we can try
                            try:
                                if not supported:
                                    # Try to dim the text (may not work on all platforms)
                                    control.configure(foreground=UNSUPPORTED_FG)
                                else:
                                    control.configure(foreground=SUPPORTED_FG)
                            except Exception:
                                # Some ttk themes don't support foreground
                                pass
                        elif isinstance(control, tk.Entry):
                            control.config(
                                state=state,
                                fg=fg_color,
                                bg=bg_color if state == "normal" else UNSUPPORTED_BG,
                                disabledforeground=UNSUPPORTED_FG,
                                disabledbackground=UNSUPPORTED_BG,
                            )
                        elif isinstance(control, tk.Checkbutton):
                            control.config(
                                state=state,
                                fg=fg_color,
                                disabledforeground=UNSUPPORTED_FG,
                            )
                        else:
                            # Generic fallback
                            control.config(state=state)
                    except tk.TclError as e:
                        logger.debug(f"Could not configure {param_name} control: {e}")

                # Update associated labels
                for label in labels:
                    if label is not None:
                        try:
                            label.config(fg=fg_color)
                        except tk.TclError as e:
                            logger.debug(f"Could not configure {param_name} label: {e}")

            # Update info label to show model capability status
            if hasattr(self, "video_settings_info"):
                key_params = {
                    "seed",
                    "aspect_ratio",
                    "resolution",
                    "camera_fixed",
                    "generate_audio",
                }
                supported_count = len(key_params & supported_params)

                if supported_count == len(key_params):
                    status_text = "All params supported"
                    status_color = COLORS["success"]
                elif supported_count == 0:
                    status_text = "Limited params"
                    status_color = COLORS["warning"]
                else:
                    status_text = f"{supported_count}/{len(key_params)} params"
                    status_color = COLORS["text_dim"]

                self.video_settings_info.config(
                    text=f"({status_text})", fg=status_color
                )

            # Show parameter support status in diagnostic label (for debugging)
            if hasattr(self, "schema_diagnostic_label"):
                param_icons = []
                for param in ["duration", "aspect_ratio", "resolution", "seed", "camera_fixed"]:
                    icon = "✓" if param in supported_params else "✗"
                    param_icons.append(f"{icon}{param[:3]}")
                self.schema_diagnostic_label.config(text=" | ".join(param_icons))

            logger.debug(
                f"Updated parameter visibility for {model_endpoint}: {len(supported_params)} supported"
            )

        except Exception as e:
            logger.error(f"Failed to update parameter visibility: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Show error to user in GUI
            if hasattr(self, "schema_diagnostic_label"):
                self.schema_diagnostic_label.config(
                    text="⚠ Schema fetch failed - check logs",
                    fg=COLORS.get("error", "#FF6464")
                )

