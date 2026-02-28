"""
Config Panel Widget - Model selection, output mode, and prompt editing.
With dynamic model fetching from fal.ai API.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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
from model_metadata import MODEL_METADATA

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
        **kwargs,
    ):
        """
        Initialize the config panel.

        Args:
            parent: Parent widget
            config: Current configuration dict
            on_config_changed: Callback when config changes
        """
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.config = config
        self.on_config_changed = on_config_changed

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
        """Set up the configuration UI."""
        # Header
        header = tk.Label(
            self,
            text="⚙ CONFIGURATION",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        header.pack(fill=tk.X, padx=10, pady=(5, 10))

        # Main config frame
        config_frame = tk.Frame(self, bg=COLORS["bg_input"], padx=10, pady=10)
        config_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._config_frame = config_frame

        # Row 1: Model selection
        row1 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row1.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            row1,
            text="MODEL",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        # Display model name in a recessed box
        model_name = self.config.get("model_display_name", "Kling 2.5 Turbo Pro")
        self.model_label = tk.Label(
            row1,
            text=model_name,
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_main"],
            fg=COLORS["accent_blue"],
            padx=12,
            pady=6,
            anchor="w",
            width=35,
            relief=tk.FLAT,
        )
        self.model_label.pack(side=tk.LEFT, padx=(5, 10))

        # Model Info container
        info_frame = tk.Frame(row1, bg=COLORS["bg_input"])
        info_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.duration_label = tk.Label(
            info_frame,
            text="10s duration",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        )
        self.duration_label.pack(side=tk.TOP, anchor="w")

        # Row 2: Output mode
        row2 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row2.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            row2,
            text="OUTPUT",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.output_mode_var = tk.StringVar(value="source")
        self.source_radio = tk.Radiobutton(
            row2,
            text="Same as Source",
            variable=self.output_mode_var,
            value="source",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_output_mode_changed,
        )
        self.source_radio.pack(side=tk.LEFT, padx=(5, 10))

        self.custom_radio = tk.Radiobutton(
            row2,
            text="Custom Folder:",
            variable=self.output_mode_var,
            value="custom",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_output_mode_changed,
        )
        self.custom_radio.pack(side=tk.LEFT)

        self.output_path_var = tk.StringVar()
        self.output_entry = tk.Entry(
            row2,
            textvariable=self.output_path_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            disabledbackground=COLORS["bg_input"],
            disabledforeground=COLORS["text_dim"],
            width=30,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.output_entry.pack(side=tk.LEFT, padx=8, pady=2, fill=tk.Y)

        self.browse_btn = tk.Button(
            row2,
            text="BROWSE",
            font=("Segoe UI", 8, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            padx=10,
            relief=tk.FLAT,
            command=self._browse_output_folder,
        )
        self.browse_btn.pack(side=tk.LEFT, padx=2)

        # Separator
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(2, 12))

        # Row 3: Prompt controls
        row3 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row3.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            row3,
            text="PROMPT",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.edit_prompt_border = tk.Frame(
            row3,
            bg=COLORS["accent_blue"],
            padx=1,
            pady=1,
        )
        self.edit_prompt_border.pack(side=tk.LEFT, padx=(5, 20))

        self.edit_prompt_btn = tk.Button(
            self.edit_prompt_border,
            text="✎ EDIT PROMPT / CHANGE MODEL",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            padx=15,
            pady=4,
            relief=tk.FLAT,
            borderwidth=0,
            command=self._show_prompt_editor,
        )
        self.edit_prompt_btn.pack()

        tk.Label(
            row3,
            text="SLOT:",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT)

        # Slot container for 2-row layout (5 slots per row)
        slot_container = tk.Frame(row3, bg=COLORS["bg_input"])
        slot_container.pack(side=tk.LEFT, padx=(5, 0))
        self._prompt_row = row3
        self._slot_container = slot_container

        slot_row1 = tk.Frame(slot_container, bg=COLORS["bg_input"])
        slot_row1.pack(side=tk.TOP)

        slot_row2 = tk.Frame(slot_container, bg=COLORS["bg_input"])
        slot_row2.pack(side=tk.TOP, pady=(2, 0))

        self.slot_var = tk.IntVar(value=1)
        for i in range(1, 11):  # 10 slots
            # Choose which row based on slot number
            parent_row = slot_row1 if i <= 5 else slot_row2
            rb = tk.Radiobutton(
                parent_row,
                text=str(i),
                variable=self.slot_var,
                value=i,
                font=("Segoe UI", 9, "bold"),
                bg=COLORS["bg_input"],
                fg=COLORS["text_light"],
                selectcolor=COLORS["bg_main"],
                activebackground=COLORS["bg_input"],
                activeforeground=COLORS["accent_blue"],
                indicatoron=False,  # Make them look like toggle buttons
                width=2,
                relief=tk.FLAT,
                command=self._on_slot_changed,
            )
            rb.pack(side=tk.LEFT, padx=1)

        # Prompt preview (multi-line, recessed look)
        preview_shell = tk.Frame(
            config_frame,
            bg=COLORS["bg_panel"],
            highlightthickness=1,
            highlightbackground=COLORS["bg_input"],
        )
        self.prompt_preview_container = preview_shell

        preview_container = tk.Frame(
            preview_shell,
            bg=COLORS["bg_panel"],
            padx=8,
            pady=6,
        )
        preview_container.pack(fill=tk.BOTH, expand=True)

        self.prompt_preview = tk.Text(
            preview_container,
            font=("Segoe UI", 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
            height=6,  # 6 lines tall for better visibility
            width=40,
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=0,
            state=tk.DISABLED,  # Read-only
            cursor="arrow",
        )

        preview_scroll = ttk.Scrollbar(
            preview_container, orient=tk.VERTICAL, command=self.prompt_preview.yview
        )
        self.prompt_preview.configure(yscrollcommand=preview_scroll.set)

        self.prompt_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure tag for bold titles
        self.prompt_preview.tag_configure(
            "title", font=("Segoe UI", 9, "bold"), foreground=COLORS["text_light"]
        )

        # Position prompt preview without affecting row height
        self._position_prompt_preview()
        config_frame.bind("<Configure>", lambda e: self._position_prompt_preview())

        # Row 4: Loop Video option
        row4 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row4.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            row4,
            text="Options:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.loop_video_var = tk.BooleanVar(value=False)
        self.loop_checkbox = tk.Checkbutton(
            row4,
            text="Loop Video (ping-pong effect)",
            variable=self.loop_video_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_loop_changed,
        )
        self.loop_checkbox.pack(side=tk.LEFT, padx=5)

        self.loop_info_label = tk.Label(
            row4,
            text="(requires FFmpeg)",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        )
        self.loop_info_label.pack(side=tk.LEFT, padx=5)

        # Row 5: Reprocess options
        row5 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row5.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            row5,
            text="",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.reprocess_var = tk.BooleanVar(value=False)
        self.reprocess_checkbox = tk.Checkbutton(
            row5,
            text="Allow reprocessing",
            variable=self.reprocess_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_reprocess_changed,
        )
        self.reprocess_checkbox.pack(side=tk.LEFT, padx=5)

        # Reprocess mode radio buttons (initially hidden)
        self.reprocess_mode_frame = tk.Frame(row5, bg=COLORS["bg_input"])
        self.reprocess_mode_frame.pack(side=tk.LEFT, padx=(10, 0))

        self.reprocess_mode_var = tk.StringVar(value="increment")

        self.overwrite_radio = tk.Radiobutton(
            self.reprocess_mode_frame,
            text="Overwrite",
            variable=self.reprocess_mode_var,
            value="overwrite",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_reprocess_mode_changed,
        )
        self.overwrite_radio.pack(side=tk.LEFT, padx=2)

        self.increment_radio = tk.Radiobutton(
            self.reprocess_mode_frame,
            text="Increment (_2, _3...)",
            variable=self.reprocess_mode_var,
            value="increment",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_reprocess_mode_changed,
        )
        self.increment_radio.pack(side=tk.LEFT, padx=2)

        # Initially hide reprocess mode options
        self._update_reprocess_mode_visibility()

        # Row 6: Verbose logging toggle
        row6 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row6.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            row6,
            text="Logging:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.verbose_gui_var = tk.BooleanVar(value=False)
        self.verbose_checkbox = tk.Checkbutton(
            row6,
            text="Verbose Mode",
            variable=self.verbose_gui_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_verbose_changed,
        )
        self.verbose_checkbox.pack(side=tk.LEFT, padx=5)

        self.verbose_info_label = tk.Label(
            row6,
            text="(show detailed processing info)",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        )
        self.verbose_info_label.pack(side=tk.LEFT, padx=5)

        # Row 7: Folder Filter options
        row7 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row7.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            row7,
            text="Folder:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.folder_pattern_var = tk.StringVar(value="")
        self.folder_pattern_entry = tk.Entry(
            row7,
            textvariable=self.folder_pattern_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            width=20,
        )
        self.folder_pattern_entry.pack(side=tk.LEFT, padx=5)
        self.folder_pattern_entry.bind("<FocusOut>", self._on_folder_pattern_changed)
        self.folder_pattern_entry.bind("<Return>", self._on_folder_pattern_changed)

        tk.Label(
            row7,
            text="Match:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT, padx=(10, 5))

        self.folder_match_mode_var = tk.StringVar(value="partial")
        self.partial_radio = tk.Radiobutton(
            row7,
            text="Partial",
            variable=self.folder_match_mode_var,
            value="partial",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_folder_match_mode_changed,
        )
        self.partial_radio.pack(side=tk.LEFT, padx=2)

        self.exact_radio = tk.Radiobutton(
            row7,
            text="Exact",
            variable=self.folder_match_mode_var,
            value="exact",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_folder_match_mode_changed,
        )
        self.exact_radio.pack(side=tk.LEFT, padx=2)

        # Row 8: Advanced Video Settings - Aspect Ratio and Resolution
        row8 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row8.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            row8,
            text="Video:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        tk.Label(
            row8,
            text="Aspect:",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.aspect_ratio_var = tk.StringVar(value="9:16")
        self.aspect_ratio_combo = ttk.Combobox(
            row8,
            textvariable=self.aspect_ratio_var,
            values=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
            state="readonly",
            width=6,
            font=("Segoe UI", 8),
            style="Dark.TCombobox",
        )
        self.aspect_ratio_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.aspect_ratio_combo.bind(
            "<<ComboboxSelected>>", self._on_aspect_ratio_changed
        )

        tk.Label(
            row8,
            text="Resolution:",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.resolution_var = tk.StringVar(value="720p")
        self.resolution_combo = ttk.Combobox(
            row8,
            textvariable=self.resolution_var,
            values=["480p", "720p"],
            state="readonly",
            width=5,
            font=("Segoe UI", 8),
            style="Dark.TCombobox",
        )
        self.resolution_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.resolution_combo.bind("<<ComboboxSelected>>", self._on_resolution_changed)

        # Duration selector
        tk.Label(
            row8,
            text="Duration:",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.duration_var = tk.StringVar(value="10s")
        self.duration_combo = ttk.Combobox(
            row8,
            textvariable=self.duration_var,
            values=["5s", "10s"],  # Default options, updated dynamically
            state="readonly",
            width=5,
            font=("Segoe UI", 8),
            style="Dark.TCombobox",
        )
        self.duration_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.duration_combo.bind("<<ComboboxSelected>>", self._on_duration_changed)

        # Schema diagnostic display (shows parameter support status)
        self.schema_diagnostic_label = tk.Label(
            row8,
            text="",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"]
        )
        self.schema_diagnostic_label.pack(side=tk.LEFT, padx=5)

        self.video_settings_info = tk.Label(
            row8,
            text="(model-dependent)",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        )
        self.video_settings_info.pack(side=tk.LEFT, padx=5)

        # Row 9: Seed and additional options
        row9 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row9.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            row9,
            text="Options:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)

        tk.Label(
            row9,
            text="Seed:",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.seed_var = tk.StringVar(value="-1")
        self.seed_entry = tk.Entry(
            row9,
            textvariable=self.seed_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            width=10,
        )
        self.seed_entry.pack(side=tk.LEFT, padx=(0, 3))
        self.seed_entry.bind("<FocusOut>", self._on_seed_changed)
        self.seed_entry.bind("<Return>", self._on_seed_changed)

        self.random_seed_var = tk.BooleanVar(value=True)
        self.random_seed_checkbox = tk.Checkbutton(
            row9,
            text="Random",
            variable=self.random_seed_var,
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_random_seed_changed,
        )
        self.random_seed_checkbox.pack(side=tk.LEFT, padx=(0, 20))

        self.camera_fixed_var = tk.BooleanVar(value=False)
        self.camera_fixed_checkbox = tk.Checkbutton(
            row9,
            text="Camera Fixed",
            variable=self.camera_fixed_var,
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_camera_fixed_changed,
        )
        self.camera_fixed_checkbox.pack(side=tk.LEFT, padx=(0, 20))

        self.generate_audio_var = tk.BooleanVar(value=False)
        self.generate_audio_checkbox = tk.Checkbutton(
            row9,
            text="Generate Audio",
            variable=self.generate_audio_var,
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_generate_audio_changed,
        )
        self.generate_audio_checkbox.pack(side=tk.LEFT, padx=(0, 5))

        # Initialize seed entry state based on random checkbox
        self._update_seed_entry_state()

    def _load_config(self):
        """Load configuration values into UI."""
        # Model (display only - set via CLI)
        model_name = self.config.get("model_display_name", "Kling 2.5 Turbo Pro")
        self.model_label.config(text=model_name)

        # Output mode
        if self.config.get("use_source_folder", True):
            self.output_mode_var.set("source")
        else:
            self.output_mode_var.set("custom")
        self.output_path_var.set(self.config.get("output_folder", ""))
        self._update_output_entry_state()

        # Prompt slot
        self.slot_var.set(self.config.get("current_prompt_slot", 1))
        self._update_prompt_preview()

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
        """Handle prompt slot change."""
        slot = self.slot_var.get()
        self.config["current_prompt_slot"] = slot
        self._update_prompt_preview()
        self._notify_change(f"Prompt slot changed to {slot}")

    def _update_prompt_preview(self):
        """Update the prompt preview text widget."""
        slot = self.slot_var.get()
        saved_prompts = self.config.get("saved_prompts", {})
        saved_titles = self.config.get("prompt_titles", {})
        prompt = saved_prompts.get(str(slot), "")
        title = saved_titles.get(str(slot), "")

        # Enable editing, update text, then disable again
        self.prompt_preview.config(state=tk.NORMAL)
        self.prompt_preview.delete("1.0", tk.END)

        if title:
            # Show title prominently with bold tag
            self.prompt_preview.insert("1.0", f"📌 {title}\n", "title")
            if prompt:
                self.prompt_preview.insert(tk.END, prompt)
        elif prompt:
            self.prompt_preview.insert("1.0", prompt)
        else:
            self.prompt_preview.insert("1.0", "(empty)")

        self.prompt_preview.config(state=tk.DISABLED)

    def _show_prompt_editor(self):
        """Show the prompt editor dialog."""
        dialog = PromptEditorDialog(self.winfo_toplevel(), config=self.config)

        if dialog.result is not None:
            # Update ALL saved prompts (user may have edited multiple slots)
            if "all_prompts" in dialog.result:
                self.config["saved_prompts"] = dialog.result["all_prompts"]
            else:
                # Fallback: just update the current slot
                saved_prompts = self.config.get("saved_prompts", {})
                saved_prompts[str(dialog.result["slot"])] = dialog.result["prompt"]
                self.config["saved_prompts"] = saved_prompts

            # Update negative prompts
            if "all_negative_prompts" in dialog.result:
                self.config["negative_prompts"] = dialog.result["all_negative_prompts"]

            # Update slot titles
            if "all_titles" in dialog.result:
                self.config["prompt_titles"] = dialog.result["all_titles"]

            # Persist capability cache
            if "model_capabilities" in dialog.result:
                self.config["model_capabilities"] = dialog.result["model_capabilities"]

            # Update current slot
            self.config["current_prompt_slot"] = dialog.result["slot"]
            self.slot_var.set(dialog.result["slot"])

            # Update model if changed
            self.config["current_model"] = dialog.result["model_endpoint"]
            self.config["model_display_name"] = dialog.result["model_name"]
            self.model_label.config(text=dialog.result["model_name"])

            # Update parameter visibility based on new model's capabilities
            self.update_parameter_visibility(dialog.result["model_endpoint"])

            # Update duration based on model
            self.config["video_duration"] = dialog.result["duration"]
            self.duration_var.set(f"{dialog.result['duration']}s")

            self._update_prompt_preview()
            self._notify_change(
                f"Settings updated: {dialog.result['model_name']}, slot {dialog.result['slot']}"
            )

    def _notify_change(self, description: Optional[str] = None):
        """Notify that config has changed."""
        if self.on_config_changed:
            self.on_config_changed(self.config, description)

    def _position_prompt_preview(self):
        """Place prompt preview over the config area without shifting rows."""
        if not hasattr(self, "prompt_preview_container"):
            return
        if not hasattr(self, "_config_frame"):
            return
        if not hasattr(self, "_prompt_row"):
            return
        if not hasattr(self, "_slot_container"):
            return

        try:
            self.update_idletasks()
            config_frame = self._config_frame
            row3_y = self._prompt_row.winfo_y()
            slot_x = self._slot_container.winfo_x()
            slot_w = self._slot_container.winfo_width()

            panel_config = {}
            if hasattr(self, "_ui_config"):
                panel_config = self._ui_config.get("config_panel", {})

            try:
                offset_x = int(panel_config.get("prompt_preview_offset_x", 16))
            except (TypeError, ValueError):
                offset_x = 16
            try:
                right_pad = int(panel_config.get("prompt_preview_right_pad", 0))
            except (TypeError, ValueError):
                right_pad = 0

            x = slot_x + slot_w + offset_x
            y = row3_y
            max_width = config_frame.winfo_width() - x - right_pad
            width = max_width if max_width > 0 else 220
            height = self.prompt_preview.winfo_reqheight() + 16

            self.prompt_preview_container.place(
                x=x,
                y=y,
                width=width,
                height=height,
            )
            self.prompt_preview_container.lift()
        except Exception:
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
            negative_height = int(config_panel.get("negative_prompt_height", 1))
        except (TypeError, ValueError):
            return

        if hasattr(self, "prompt_preview"):
            self.prompt_preview.config(
                height=max(1, preview_height),
                font=("Segoe UI", max(6, preview_font_size)),
            )
            self.prompt_preview.tag_configure(
                "title",
                font=("Segoe UI", max(6, preview_font_size), "bold"),
                foreground=COLORS["text_light"],
            )

        if hasattr(self, "prompt_preview_container"):
            try:
                preview_width = int(config_panel.get("prompt_preview_width", 0))
            except (TypeError, ValueError):
                preview_width = 0
            if preview_width > 0:
                try:
                    self.prompt_preview_container.place_configure(width=preview_width)
                except Exception:
                    pass

        if hasattr(self, "neg_entry"):
            ipady = max(0, (max(1, negative_height) - 1) * 4)
            try:
                self.neg_entry.pack_configure(ipady=ipady)
            except Exception:
                pass

        self._position_prompt_preview()

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
            "slot_var",
            "loop_video_var",
            "reprocess_var",
            "reprocess_mode_var",
            "verbose_gui_var",
            "folder_pattern_var",
            "folder_match_mode_var",
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
                            text="(No API key – capabilities unknown)",
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


class PromptEditorDialog(tk.Toplevel):
    """Modal dialog for editing prompts with slot and model selection."""

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.title("Edit Prompt & Settings")
        self.result = None
        self.config = config
        # Pre-set attributes so event callbacks remain safe even if UI setup aborts early
        self.text: Optional[tk.Text] = None
        self.custom_status: Optional[tk.Label] = None
        self.prompt_label: Optional[tk.Label] = None
        self.duration_label: Optional[tk.Label] = None
        self.neg_badge: Optional[tk.Label] = None
        self.neg_status: Optional[tk.Label] = None
        self.neg_entry: Optional[tk.Entry] = None
        self.char_count: Optional[tk.Label] = None
        self.refresh_btn: Optional[tk.Button] = None
        self.model_status: Optional[tk.Label] = None
        self.model_combo: Optional[ttk.Combobox] = None
        self.custom_entry: Optional[tk.Entry] = None
        self.neg_var: Optional[tk.StringVar] = None
        self.title_var: Optional[tk.StringVar] = None
        self.title_entry: Optional[tk.Entry] = None

        # IMPORTANT: Make a deep copy so cancel doesn't affect original config
        original_prompts = config.get("saved_prompts", {})
        original_negative_prompts = config.get("negative_prompts", {})
        original_titles = config.get("prompt_titles", {})
        self.capabilities = config.get("model_capabilities", {})
        self.saved_prompts = {k: (v if v else "") for k, v in original_prompts.items()}
        self.saved_negative_prompts = {
            k: (v if v else "") for k, v in original_negative_prompts.items()
        }
        self.saved_titles = {k: (v if v else "") for k, v in original_titles.items()}

        # Model list - start with cached/fallback, then fetch fresh
        self.models = ModelFetcher.get_cached_or_fallback(config)
        self.is_loading_models = False

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Configure window
        self.configure(bg=COLORS["bg_panel"])
        self.geometry("900x820")
        self.minsize(720, 560)

        # Increase Combobox dropdown height to show more models at once
        # Scoped to toplevel window to avoid affecting other windows in the process
        # Guarded to prevent crashes in headless or unusual Tk backend environments
        try:
            root = self.winfo_toplevel()
            root.option_add("*TCombobox*Listbox.height", COMBOBOX_DROPDOWN_HEIGHT)
        except tk.TclError as e:
            logger.warning("Failed to set combobox dropdown height: %s", e)

        # Style to ensure Combobox text is visible on dark background
        # NOTE: Do NOT use style.theme_use() - it breaks global ttk rendering
        style = ttk.Style(self)
        style.configure(
            "Dialog.TCombobox",
            fieldbackground=COLORS["bg_input"],
            background=COLORS["bg_panel"],
            foreground="#000000",  # Black text on light combobox
            arrowcolor=COLORS["text_light"],
        )
        # Map ensures text is visible in all states
        style.map(
            "Dialog.TCombobox",
            fieldbackground=[("readonly", COLORS["bg_input"]), ("disabled", "#666666")],
            foreground=[("readonly", "#000000"), ("disabled", "#999999")],
            selectbackground=[("readonly", COLORS["accent_blue"])],
            selectforeground=[("readonly", "#FFFFFF")],
        )

        # Create UI
        self._setup_ui()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        # Fetch fresh models if API key exists
        api_key = config.get("falai_api_key", "")
        if api_key:
            self._refresh_models()

        # Wait for dialog to close
        self.wait_window()

    def _setup_ui(self):
        """Set up the dialog UI with slot and model selectors."""
        # Title
        tk.Label(
            self,
            text="✏️ PROMPT & MODEL SETTINGS",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(padx=10, pady=(10, 5), anchor="w")

        # Top controls frame
        controls_frame = tk.Frame(self, bg=COLORS["bg_input"], padx=10, pady=10)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        # Row 1: Slot Selection
        slot_row = tk.Frame(controls_frame, bg=COLORS["bg_input"])
        slot_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            slot_row,
            text="Prompt Slot:",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=12,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.slot_var = tk.IntVar(value=self.config.get("current_prompt_slot", 1))
        self.current_slot = (
            self.slot_var.get()
        )  # Track current slot for saving before switch

        for i in range(1, 11):  # 10 slots
            rb = tk.Radiobutton(
                slot_row,
                text=f"{i}",
                variable=self.slot_var,
                value=i,
                font=("Segoe UI", 9),
                bg=COLORS["bg_input"],
                fg=COLORS["text_light"],
                selectcolor=COLORS["bg_main"],
                activebackground=COLORS["bg_input"],
                activeforeground=COLORS["text_light"],
                command=self._on_slot_changed,
            )
            rb.pack(side=tk.LEFT, padx=4)

        # Row 1.5: Title field for current slot
        title_row = tk.Frame(controls_frame, bg=COLORS["bg_input"])
        title_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            title_row,
            text="Slot Title:",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=12,
            anchor="w",
        ).pack(side=tk.LEFT)

        current_slot = self.config.get("current_prompt_slot", 1)
        self.title_var = tk.StringVar(
            value=self.saved_titles.get(str(current_slot), "")
        )
        self.title_entry = tk.Entry(
            title_row,
            textvariable=self.title_var,
            font=("Segoe UI", 10),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            width=40,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.title_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        tk.Label(
            title_row,
            text="(optional - for easy identification)",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT, padx=5)

        # Row 2: Model Selection
        model_row = tk.Frame(controls_frame, bg=COLORS["bg_input"])
        model_row.pack(fill=tk.X, pady=(0, 5))

        tk.Label(
            model_row,
            text="Model:",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=12,
            anchor="w",
        ).pack(side=tk.LEFT)

        # Find current model index
        current_model = self.config.get("current_model", "")
        model_names = [m["name"] for m in self.models]
        current_index = 0
        for i, m in enumerate(self.models):
            if m["endpoint"] == current_model:
                current_index = i
                break

        self.model_var = tk.StringVar(
            value=model_names[current_index] if model_names else "Loading..."
        )
        self.model_combo = ttk.Combobox(
            model_row,
            textvariable=self.model_var,
            values=model_names,
            state="readonly",
            font=("Segoe UI", 10),
            width=28,
            style="Dialog.TCombobox",
        )
        self.model_combo.pack(side=tk.LEFT, padx=5)
        if model_names:
            self.model_combo.current(current_index)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_changed)

        # Refresh button
        self.refresh_btn = tk.Button(
            model_row,
            text="🔄",
            font=("Segoe UI", 10),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            width=3,
            command=self._refresh_models,
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=2)

        # Duration label
        duration = self.models[current_index]["duration"] if self.models else 10
        self.duration_label = tk.Label(
            model_row,
            text=f"Duration: {duration}s",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["accent_blue"],
        )
        self.duration_label.pack(side=tk.LEFT, padx=5)

        # Model count and status
        self.model_status = tk.Label(
            model_row,
            text=f"({len(self.models)} models)",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        )
        self.model_status.pack(side=tk.LEFT, padx=5)

        # Negative prompt row (capability-aware)
        neg_row = tk.Frame(controls_frame, bg=COLORS["bg_input"])
        neg_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            neg_row,
            text="Negative:",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=12,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.neg_var = tk.StringVar(
            value=self.saved_negative_prompts.get(str(self.slot_var.get()), "")
        )
        self.neg_entry = tk.Entry(
            neg_row,
            textvariable=self.neg_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            width=60,
        )
        self.neg_entry.pack(side=tk.LEFT, padx=5, pady=2, fill=tk.X, expand=True)

        self.neg_badge = tk.Label(
            neg_row,
            text="Checking",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS.get("warning", "#FFB347"),
            fg="#1a1a1a",
            padx=8,
            pady=3,
        )
        self.neg_badge.pack(side=tk.LEFT, padx=6)

        self.neg_status = tk.Label(
            neg_row,
            text="Checking support...",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        )
        self.neg_status.pack(side=tk.LEFT, padx=5)

        # Kick off capability check for initially selected model
        if self.models:
            self._check_negative_support(self.models[current_index]["endpoint"])
        else:
            self.neg_status.config(
                text="No models loaded", fg=COLORS.get("warning", "#FFB347")
            )
            self.neg_entry.config(state="disabled")

        # Row 3: Browse models link
        link_row = tk.Frame(controls_frame, bg=COLORS["bg_input"])
        link_row.pack(fill=tk.X)

        tk.Label(link_row, text="", bg=COLORS["bg_input"], width=12).pack(side=tk.LEFT)

        browse_link = tk.Label(
            link_row,
            text="📋 Browse all models on fal.ai →",
            font=("Segoe UI", 9, "underline"),
            bg=COLORS["bg_input"],
            fg=COLORS["accent_blue"],
            cursor="hand2",
        )
        browse_link.pack(side=tk.LEFT, padx=5)
        browse_link.bind(
            "<Button-1>",
            lambda e: os.startfile(FAL_MODELS_URL) if os.name == "nt" else None,
        )

        # Row 4: Custom model endpoint entry
        custom_row = tk.Frame(controls_frame, bg=COLORS["bg_input"])
        custom_row.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            custom_row,
            text="Custom:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
            width=12,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.custom_endpoint_var = tk.StringVar(value="")
        self.custom_entry = tk.Entry(
            custom_row,
            textvariable=self.custom_endpoint_var,
            font=("Consolas", 9),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            width=40,
        )
        self.custom_entry.pack(side=tk.LEFT, padx=5)

        # Placeholder text
        self.custom_entry.insert(0, "fal-ai/kling-video/v2.5/pro/image-to-video")
        self.custom_entry.config(fg=COLORS["text_dim"])

        def on_custom_focus_in(e):
            if not self.custom_entry:
                return
            if self.custom_entry.get() == "fal-ai/kling-video/v2.5/pro/image-to-video":
                self.custom_entry.delete(0, tk.END)
                self.custom_entry.config(fg=COLORS["text_light"])

        def on_custom_focus_out(e):
            if not self.custom_entry:
                return
            if not self.custom_entry.get().strip():
                self.custom_entry.insert(
                    0, "fal-ai/kling-video/v2.5/pro/image-to-video"
                )
                self.custom_entry.config(fg=COLORS["text_dim"])

        self.custom_entry.bind("<FocusIn>", on_custom_focus_in)
        self.custom_entry.bind("<FocusOut>", on_custom_focus_out)

        self.use_custom_btn = tk.Button(
            custom_row,
            text="Use Custom",
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            command=self._use_custom_endpoint,
        )
        self.use_custom_btn.pack(side=tk.LEFT, padx=5)

        # Custom endpoint status
        self.custom_status = tk.Label(
            custom_row,
            text="",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
        )
        self.custom_status.pack(side=tk.LEFT, padx=5)

        # Prompt label
        prompt_label_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        prompt_label_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        self.prompt_label = tk.Label(
            prompt_label_frame,
            text=f"Prompt for Slot {self.slot_var.get()}:",
            font=("Segoe UI", 10),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        self.prompt_label.pack(side=tk.LEFT)

        # Character count
        self.char_count = tk.Label(
            prompt_label_frame,
            text="0 chars",
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.char_count.pack(side=tk.RIGHT)

        # Text area with scrollbar
        text_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5, side=tk.TOP)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text.yview)

        # Bind text changes for character count
        self.text.bind("<KeyRelease>", self._update_char_count)

        # Load initial prompt for current slot
        self._load_prompt_for_slot(self.slot_var.get())

        # Button frame
        btn_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        btn_frame.pack(fill=tk.X, padx=10, pady=10, side=tk.BOTTOM)

        # Info label
        tk.Label(
            btn_frame,
            text="💾 Changes are saved to kling_config.json",
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT)

        # Cancel button
        tk.Button(
            btn_frame,
            text="✖ Cancel",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=12,
            command=self._cancel,
        ).pack(side=tk.RIGHT, padx=5, pady=(5, 0))

        # Save button
        tk.Button(
            btn_frame,
            text="💾 Save",
            font=("Segoe UI", 10, "bold"),
            bg="#329632",
            fg="white",
            width=12,
            command=self._save,
        ).pack(side=tk.RIGHT, padx=5, pady=(5, 0))

    def _on_slot_changed(self):
        """Handle slot selection change - save current and load new slot's prompt."""
        # Guard: ensure UI widgets are initialized before accessing them
        if (
            not self.text
            or not self.prompt_label
            or not self.neg_var
            or not self.title_var
        ):
            return

        # Save current slot's text before switching
        current_text = self.text.get("1.0", tk.END).strip()
        self.saved_prompts[str(self.current_slot)] = current_text
        self.saved_negative_prompts[str(self.current_slot)] = self.neg_var.get().strip()
        self.saved_titles[str(self.current_slot)] = self.title_var.get().strip()

        # Switch to new slot
        new_slot = self.slot_var.get()
        self.current_slot = new_slot
        self.prompt_label.config(text=f"Prompt for Slot {new_slot}:")
        self._load_prompt_for_slot(new_slot)

    def _load_prompt_for_slot(self, slot: int):
        """Load prompt text for the specified slot."""
        if not self.text or not self.neg_var or not self.title_var:
            return

        prompt = self.saved_prompts.get(str(slot), "") or ""
        neg_prompt = self.saved_negative_prompts.get(str(slot), "") or ""
        title = self.saved_titles.get(str(slot), "") or ""
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", prompt)
        self.neg_var.set(neg_prompt)
        self.title_var.set(title)
        self._update_char_count()

    def _on_model_changed(self, event=None):
        """Handle model selection change and update duration options."""
        # Guard: ensure UI widgets are initialized before accessing them
        if not self.custom_status or not self.duration_label:
            return

        model_name = self.model_var.get()
        for m in self.models:
            if m["name"] == model_name:
                # Get duration options from new metadata structure
                duration_options = m.get("duration_options", m.get("duration", [5, 10]))
                if isinstance(duration_options, int):
                    duration_options = [duration_options]
                duration_default = m.get("duration_default", duration_options[0] if duration_options else 10)

                # Update duration label in dialog
                self.duration_label.config(text=f"Duration: {duration_default}s")

                # Update parent ConfigPanel's duration dropdown
                if hasattr(self.parent, 'duration_combo'):
                    self.parent.duration_combo["values"] = [f"{d}s" for d in duration_options]

                    # Set to default if current duration not valid for new model
                    current_duration = self.config.get("video_duration", 10)
                    if current_duration not in duration_options:
                        self.parent.duration_var.set(f"{duration_default}s")
                        self.config["video_duration"] = duration_default
                        logger.info(f"Duration adjusted to {duration_default}s for model {model_name}")

                # Clear custom status when selecting from dropdown
                self.custom_status.config(text="", fg=COLORS["text_dim"])
                self._check_negative_support(m.get("endpoint", m.get("endpoint_id", "")))
                break

    def _use_custom_endpoint(self):
        """Use the custom endpoint from the entry field."""
        if (
            not self.custom_entry
            or not self.custom_status
            or not self.model_combo
            or not self.duration_label
        ):
            return

        custom_endpoint = self.custom_entry.get().strip()
        placeholder = "fal-ai/kling-video/v2.5/pro/image-to-video"

        if not custom_endpoint or custom_endpoint == placeholder:
            self.custom_status.config(text="Enter endpoint first", fg="#FF6464")
            return

        # Validate format (should start with fal-ai/ or be a valid path)
        if not custom_endpoint.startswith("fal-ai/") and "/" not in custom_endpoint:
            self.custom_status.config(text="Invalid format", fg="#FF6464")
            return

        # Create display name from endpoint
        display_name = parse_endpoint_to_display_name(custom_endpoint)

        # Add to models list if not already there
        existing = next(
            (m for m in self.models if m["endpoint"] == custom_endpoint), None
        )
        if not existing:
            custom_model = {
                "name": f"[Custom] {display_name}",
                "endpoint": custom_endpoint,
                "duration_options": [5, 10],  # Default options for custom endpoints
                "duration_default": 10,
                "description": "Custom endpoint",
            }
            self.models.insert(0, custom_model)

            # Update dropdown
            model_names = [m["name"] for m in self.models]
            self.model_combo["values"] = model_names

        # Select the custom model
        for i, m in enumerate(self.models):
            if m["endpoint"] == custom_endpoint:
                self.model_combo.current(i)
                self.model_var.set(m["name"])
                # Get duration from new structure
                duration_default = m.get("duration_default", m.get("duration", 10))
                self.duration_label.config(text=f"Duration: {duration_default}s")
                break

        self.custom_status.config(text="✓ Custom model set", fg="#64FF64")
        # Trigger negative prompt capability check for custom endpoint
        self._check_negative_support(custom_endpoint)

    def _refresh_models(self):
        """Fetch fresh model list from fal.ai API."""
        if self.is_loading_models:
            return

        if not self.refresh_btn or not self.model_status:
            return

        api_key = self.config.get("falai_api_key", "")
        if not api_key:
            self.model_status.config(text="(No API key)", fg="#FF6464")
            return

        self.is_loading_models = True
        self.refresh_btn.config(state="disabled")
        self.model_status.config(text="(Loading...)", fg=COLORS["accent_blue"])

        def on_models_fetched(models, error):
            # Run on main thread
            self.after(0, lambda: self._update_models(models, error))

        ModelFetcher.fetch_models(api_key, on_models_fetched)

    def _check_negative_support(self, endpoint_id: str):
        """Detect if the selected model supports negative_prompt via its OpenAPI schema."""
        # Use cached capability if present
        cached = self.capabilities.get(endpoint_id)
        if cached is not None:
            self._apply_negative_support(cached)
            return

        if not self.neg_status or not self.neg_badge or not self.neg_entry:
            return

        self.neg_status.config(text="Checking support...", fg=COLORS["text_dim"])
        self.neg_badge.config(text="Checking", bg=COLORS["warning"], fg="black")
        self.neg_entry.config(state="disabled")

        def worker():
            supported = False
            try:
                import requests

                url = f"https://fal.ai/api/openapi/queue/openapi.json?endpoint_id={endpoint_id}"
                resp = requests.get(url, timeout=6)
                if resp.status_code == 200:
                    props = resp.json().get("paths", {})
                    for pdata in props.values():
                        for info in pdata.values():
                            schema_props = (
                                info.get("requestBody", {})
                                .get("content", {})
                                .get("application/json", {})
                                .get("schema", {})
                                .get("properties", {})
                            )
                            if any(
                                "negative" in k.lower() for k in schema_props.keys()
                            ):
                                supported = True
                                break
                        if supported:
                            break
            except Exception as e:
                logger.debug(f"Negative prompt capability check failed: {e}")

            # Schedule cache update and UI apply on main thread for thread safety
            def update_on_main():
                if not self.winfo_exists():
                    return
                self.capabilities[endpoint_id] = supported
                self.config["model_capabilities"] = self.capabilities
                self._apply_negative_support(supported)

            self.after(0, update_on_main)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_negative_support(self, supported: bool):
        """Enable/disable negative prompt entry based on support."""
        if not self.neg_entry or not self.neg_status or not self.neg_badge:
            return

        if supported:
            self.neg_entry.config(state="normal")
            self.neg_status.config(text="Supported by model", fg=COLORS["success"])
            self.neg_badge.config(text="✓ Supported", bg="#2E7D32", fg="#ffffff")
        else:
            self.neg_entry.delete(0, tk.END)
            self.neg_entry.config(state="disabled")
            self.neg_status.config(
                text="Not supported by this model", fg=COLORS["text_dim"]
            )
            self.neg_badge.config(text="✗ Unsupported", bg="#C62828", fg="#ffffff")

    def _update_models(self, models: list, error: str):
        """Update model dropdown with fetched models."""
        # Safety check: dialog may have been closed before callback fired
        if not self.winfo_exists():
            return

        if (
            not self.refresh_btn
            or not self.model_status
            or not self.model_combo
            or not self.duration_label
        ):
            return

        self.is_loading_models = False
        self.refresh_btn.config(state="normal")

        if error:
            self.model_status.config(text=f"(Error: {error[:20]})", fg="#FF6464")
            return

        if not models:
            self.model_status.config(text="(No models found)", fg="#FF6464")
            return

        # Update models list
        self.models = models
        ModelFetcher.cache_models(self.config, models)

        # Update dropdown
        model_names = [m["name"] for m in models]
        self.model_combo["values"] = model_names

        # Try to keep current selection
        current_endpoint = self.config.get("current_model", "")
        new_index = 0
        for i, m in enumerate(models):
            if m["endpoint"] == current_endpoint:
                new_index = i
                break

        self.model_combo.current(new_index)
        self.model_var.set(model_names[new_index])
        # Get duration from new structure
        duration_default = models[new_index].get("duration_default", models[new_index].get("duration", 10))
        self.duration_label.config(text=f"Duration: {duration_default}s")
        self.model_status.config(text=f"({len(models)} models)", fg="#64FF64")
        self._check_negative_support(models[new_index]["endpoint"])

    def _update_char_count(self, event=None):
        """Update character count label."""
        if not self.text or not self.char_count:
            return
        text = self.text.get("1.0", tk.END).strip()
        self.char_count.config(text=f"{len(text)} chars")

    def _get_selected_model(self) -> dict:
        """Get the selected model details."""
        model_name = self.model_var.get()
        for m in self.models:
            if m["name"] == model_name:
                return m
        # Fallback to first model or a default
        if self.models:
            return self.models[0]
        return {"name": "Unknown", "endpoint": "", "duration": 10}

    def _save(self):
        """Save and close with all settings."""
        if not self.text or not self.neg_var or not self.title_var:
            return

        # Save current slot's text to local dict
        current_text = self.text.get("1.0", tk.END).strip()
        self.saved_prompts[str(self.current_slot)] = current_text
        self.saved_negative_prompts[str(self.current_slot)] = self.neg_var.get().strip()
        self.saved_titles[str(self.current_slot)] = self.title_var.get().strip()

        model = self._get_selected_model()
        self.result = {
            "slot": self.slot_var.get(),
            "prompt": current_text,
            "model_name": model["name"],
            "model_endpoint": model["endpoint"],
            "duration": model["duration"],
            "all_prompts": self.saved_prompts.copy(),  # Include all edited prompts
            "all_negative_prompts": self.saved_negative_prompts.copy(),
            "all_titles": self.saved_titles.copy(),  # Include all slot titles
            "model_capabilities": self.capabilities,
        }
        self.destroy()

    def _cancel(self):
        """Cancel and close."""
        self.result = None
        self.destroy()
