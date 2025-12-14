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


# Color palette
COLORS = {
    "bg_main": "#2D2D30",
    "bg_panel": "#3C3C41",
    "bg_input": "#464649",
    "text_light": "#DCDCDC",
    "text_dim": "#B4B4B4",
    "accent_blue": "#6496FF",
    "border": "#5A5A5E",
}

# Minimal fallback - ONLY used when API fails AND no cache exists
# Models change frequently - this is just a safety net with user's preferred model
# The app dynamically fetches all available models from fal.ai API
FALLBACK_MODELS = [
    {"name": "Kling V2.5 Turbo Pro", "endpoint": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video", "duration": 10},
]

# fal.ai URLs for model browsing and API reference
FAL_MODELS_URL = "https://fal.ai/models?categories=image-to-video"
FAL_EXPLORE_URL = "https://fal.ai/explore/models"
FAL_API_DOCS_URL = "https://docs.fal.ai"

# Vague model names that should be replaced with parsed endpoint names
# Using frozenset for O(1) lookup performance
VAGUE_MODEL_NAMES = frozenset(['kling video', 'pixverse', 'wan effects', 'longcat video', 'pika'])

# UI Configuration
COMBOBOX_DROPDOWN_HEIGHT = 25  # Number of items visible in dropdown (default ~10)


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
    parts = endpoint_id.replace("fal-ai/", "").replace("/image-to-video", "").replace("/video-to-video", "")

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
    def fetch_models(api_key: str, callback: Callable[[List[Dict], Optional[str]], None]):
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
                    params = {"category": "image-to-video", "status": "active", "limit": 50}
                    if cursor:
                        params["cursor"] = cursor

                    response = requests.get(
                        "https://api.fal.ai/v1/models",
                        params=params,
                        headers=headers,
                        timeout=15
                    )

                    if response.status_code != 200:
                        callback([], f"API error: {response.status_code}")
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
                        name_lower = api_display_name.lower().strip()

                        # Check if name matches a known vague pattern (word-boundary aware to avoid false positives)
                        # e.g., 'pika' matches 'Pika Video' but not 'Pikachu Model'
                        is_vague = any(
                            re.search(rf'(?<!\w){re.escape(vague)}(?!\w)', name_lower)
                            for vague in VAGUE_MODEL_NAMES
                        )

                        # Check if name has version info (v2, v2.5, 2.1, 1.6, etc.)
                        # Match: "v" followed by digits, OR digits with decimal (not "Video 01")
                        has_version_in_name = bool(
                            re.search(r'\bv\d+(?:\.\d+)?', api_display_name, re.IGNORECASE) or
                            re.search(r'\b\d+\.\d+\b', api_display_name)  # Like "2.1" or "1.6"
                        )

                        # Check if endpoint has version info
                        has_version_in_endpoint = bool(re.search(r'/v\d+\.?\d*', endpoint_id))

                        # Use parsed name if: no API name, vague name, or endpoint has version but name doesn't
                        if not api_display_name or is_vague or (has_version_in_endpoint and not has_version_in_name):
                            display_name = parse_endpoint_to_display_name(endpoint_id)
                        else:
                            display_name = api_display_name

                        all_models.append({
                            "name": display_name,
                            "endpoint": endpoint_id,
                            "duration": metadata.get("duration_estimate", 10),
                            "description": metadata.get("description", "")[:100],
                        })

                    # Check for more pages
                    if data.get("has_more") and data.get("next_cursor"):
                        cursor = data["next_cursor"]
                    else:
                        break

                if all_models:
                    # Sort models: Kling first, then other popular models, then rest alphabetically
                    def sort_key(m):
                        name_lower = m["name"].lower()
                        endpoint_lower = m["endpoint"].lower()
                        # Priority tiers
                        if "kling" in name_lower or "kling" in endpoint_lower:
                            # Further sort Kling by version (higher versions first)
                            if "v2.6" in endpoint_lower:
                                return (0, 0, name_lower)
                            elif "v2.5" in endpoint_lower:
                                if "turbo" in endpoint_lower:
                                    return (0, 1, name_lower)
                                else:
                                    return (0, 2, name_lower)
                            else:
                                return (0, 9, name_lower)
                        elif "veo" in name_lower or "sora" in name_lower:
                            return (1, 0, name_lower)
                        elif "ltx" in name_lower or "pixverse" in name_lower:
                            return (2, 0, name_lower)
                        else:
                            return (3, 0, name_lower)

                    all_models.sort(key=sort_key)
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

        # If cache exists and is less than TTL old, use it
        if cached_list and (time.time() - cached_time) < ModelFetcher.CACHE_TTL:
            return cached_list

        return FALLBACK_MODELS

    @staticmethod
    def cache_models(config: dict, models: List[Dict]):
        """Save models to config cache."""
        config["cached_models"] = {
            "models": models,
            "timestamp": time.time()
        }


class ConfigPanel(tk.Frame):
    """Configuration panel for model, output, and prompt settings."""

    def __init__(
        self,
        parent,
        config: dict,
        on_config_changed: Callable[[dict], None],
        **kwargs
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

        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """Set up the configuration UI."""
        # Header
        header = tk.Label(
            self,
            text="⚙ CONFIGURATION",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"]
        )
        header.pack(fill=tk.X, padx=10, pady=(5, 10))

        # Main config frame
        config_frame = tk.Frame(self, bg=COLORS["bg_input"], padx=10, pady=10)
        config_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Row 1: Model selection
        row1 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row1.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            row1,
            text="Model:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w"
        ).pack(side=tk.LEFT)

        # Display model name from CLI config (read-only)
        model_name = self.config.get("model_display_name", "Kling 2.5 Turbo Pro")
        self.model_label = tk.Label(
            row1,
            text=model_name,
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["bg_main"],
            fg=COLORS["accent_blue"],
            padx=10,
            pady=4,
            anchor="w",
            width=35
        )
        self.model_label.pack(side=tk.LEFT, padx=(5, 10))

        # Duration and price labels
        self.duration_label = tk.Label(
            row1,
            text="Duration: 10s",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"]
        )
        self.duration_label.pack(side=tk.LEFT, padx=5)

        self.price_label = tk.Label(
            row1,
            text="$0.07/sec",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["accent_blue"]
        )
        self.price_label.pack(side=tk.LEFT, padx=5)

        # Row 2: Output mode
        row2 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row2.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            row2,
            text="Output:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.output_mode_var = tk.StringVar(value="source")
        self.source_radio = tk.Radiobutton(
            row2,
            text="Source Folder",
            variable=self.output_mode_var,
            value="source",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_output_mode_changed
        )
        self.source_radio.pack(side=tk.LEFT, padx=(5, 10))

        self.custom_radio = tk.Radiobutton(
            row2,
            text="Custom:",
            variable=self.output_mode_var,
            value="custom",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"],
            activebackground=COLORS["bg_input"],
            activeforeground=COLORS["text_light"],
            command=self._on_output_mode_changed
        )
        self.custom_radio.pack(side=tk.LEFT)

        self.output_path_var = tk.StringVar()
        self.output_entry = tk.Entry(
            row2,
            textvariable=self.output_path_var,
            font=("Segoe UI", 9),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            width=30
        )
        self.output_entry.pack(side=tk.LEFT, padx=5)

        self.browse_btn = tk.Button(
            row2,
            text="Browse...",
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            command=self._browse_output_folder
        )
        self.browse_btn.pack(side=tk.LEFT, padx=5)

        # Row 3: Prompt controls
        row3 = tk.Frame(config_frame, bg=COLORS["bg_input"])
        row3.pack(fill=tk.X)

        tk.Label(
            row3,
            text="Prompt:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=8,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.edit_prompt_btn = tk.Button(
            row3,
            text="Edit Prompt...",
            font=("Segoe UI", 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            command=self._show_prompt_editor
        )
        self.edit_prompt_btn.pack(side=tk.LEFT, padx=(5, 15))

        tk.Label(
            row3,
            text="Slot:",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"]
        ).pack(side=tk.LEFT)

        self.slot_var = tk.IntVar(value=1)
        for i in range(1, 4):
            rb = tk.Radiobutton(
                row3,
                text=str(i),
                variable=self.slot_var,
                value=i,
                font=("Segoe UI", 9),
                bg=COLORS["bg_input"],
                fg=COLORS["text_light"],
                selectcolor=COLORS["bg_main"],
                activebackground=COLORS["bg_input"],
                activeforeground=COLORS["text_light"],
                command=self._on_slot_changed
            )
            rb.pack(side=tk.LEFT, padx=2)

        # Prompt preview
        self.prompt_preview = tk.Label(
            row3,
            text="",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"],
            anchor="w"
        )
        self.prompt_preview.pack(side=tk.LEFT, padx=(15, 0), fill=tk.X, expand=True)

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
            anchor="w"
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
            command=self._on_loop_changed
        )
        self.loop_checkbox.pack(side=tk.LEFT, padx=5)

        self.loop_info_label = tk.Label(
            row4,
            text="(requires FFmpeg)",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"]
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
            anchor="w"
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
            command=self._on_reprocess_changed
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
            command=self._on_reprocess_mode_changed
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
            command=self._on_reprocess_mode_changed
        )
        self.increment_radio.pack(side=tk.LEFT, padx=2)

        # Initially hide reprocess mode options
        self._update_reprocess_mode_visibility()

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
        self.duration_label.config(text=f"Duration: {duration}s")

        # Loop video option
        self.loop_video_var.set(self.config.get("loop_videos", False))
        self._check_ffmpeg_status()

        # Reprocess options
        self.reprocess_var.set(self.config.get("allow_reprocess", False))
        self.reprocess_mode_var.set(self.config.get("reprocess_mode", "increment"))
        self._update_reprocess_mode_visibility()

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
        self._notify_change()

    def _on_reprocess_changed(self):
        """Handle reprocess checkbox change."""
        self.config["allow_reprocess"] = self.reprocess_var.get()
        self._update_reprocess_mode_visibility()
        self._notify_change()

    def _on_reprocess_mode_changed(self):
        """Handle reprocess mode radio change."""
        self.config["reprocess_mode"] = self.reprocess_mode_var.get()
        self._notify_change()

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
        self._notify_change()

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
            title="Select Output Folder",
            initialdir=self.output_path_var.get() or "."
        )
        if folder:
            self.output_path_var.set(folder)
            self.config["output_folder"] = folder
            self._notify_change()

    def _on_slot_changed(self):
        """Handle prompt slot change."""
        self.config["current_prompt_slot"] = self.slot_var.get()
        self._update_prompt_preview()
        self._notify_change()

    def _update_prompt_preview(self):
        """Update the prompt preview label."""
        slot = self.slot_var.get()
        saved_prompts = self.config.get("saved_prompts", {})
        prompt = saved_prompts.get(str(slot), "")

        if prompt:
            # Truncate for preview
            preview = prompt[:50] + "..." if len(prompt) > 50 else prompt
            self.prompt_preview.config(text=f"  ({preview})")
        else:
            self.prompt_preview.config(text="  (empty)")

    def _show_prompt_editor(self):
        """Show the prompt editor dialog."""
        dialog = PromptEditorDialog(
            self.winfo_toplevel(),
            config=self.config
        )

        if dialog.result is not None:
            # Update ALL saved prompts (user may have edited multiple slots)
            if "all_prompts" in dialog.result:
                self.config["saved_prompts"] = dialog.result["all_prompts"]
            else:
                # Fallback: just update the current slot
                saved_prompts = self.config.get("saved_prompts", {})
                saved_prompts[str(dialog.result["slot"])] = dialog.result["prompt"]
                self.config["saved_prompts"] = saved_prompts

            # Update current slot
            self.config["current_prompt_slot"] = dialog.result["slot"]
            self.slot_var.set(dialog.result["slot"])

            # Update model if changed
            self.config["current_model"] = dialog.result["model_endpoint"]
            self.config["model_display_name"] = dialog.result["model_name"]
            self.model_label.config(text=dialog.result["model_name"])

            # Update duration based on model
            self.config["video_duration"] = dialog.result["duration"]
            self.duration_label.config(text=f"Duration: {dialog.result['duration']}s")

            self._update_prompt_preview()
            self._notify_change()

    def _notify_change(self):
        """Notify that config has changed."""
        if self.on_config_changed:
            self.on_config_changed(self.config)

    def get_config(self) -> dict:
        """Get current configuration."""
        return self.config.copy()


class PromptEditorDialog(tk.Toplevel):
    """Modal dialog for editing prompts with slot and model selection."""

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.title("Edit Prompt & Settings")
        self.result = None
        self.config = config
        # IMPORTANT: Make a deep copy so cancel doesn't affect original config
        original_prompts = config.get("saved_prompts", {"1": "", "2": "", "3": ""})
        self.saved_prompts = {k: (v if v else "") for k, v in original_prompts.items()}

        # Model list - start with cached/fallback, then fetch fresh
        self.models = ModelFetcher.get_cached_or_fallback(config)
        self.is_loading_models = False

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Configure window
        self.configure(bg=COLORS["bg_panel"])
        self.geometry("750x620")
        self.minsize(600, 450)

        # Increase Combobox dropdown height to show more models at once
        self.option_add('*TCombobox*Listbox.height', COMBOBOX_DROPDOWN_HEIGHT)

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
            fg=COLORS["text_light"]
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
            anchor="w"
        ).pack(side=tk.LEFT)

        self.slot_var = tk.IntVar(value=self.config.get("current_prompt_slot", 1))
        self.current_slot = self.slot_var.get()  # Track current slot for saving before switch

        for i in range(1, 4):
            rb = tk.Radiobutton(
                slot_row,
                text=f"Slot {i}",
                variable=self.slot_var,
                value=i,
                font=("Segoe UI", 10),
                bg=COLORS["bg_input"],
                fg=COLORS["text_light"],
                selectcolor=COLORS["bg_main"],
                activebackground=COLORS["bg_input"],
                activeforeground=COLORS["text_light"],
                command=self._on_slot_changed
            )
            rb.pack(side=tk.LEFT, padx=10)

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
            anchor="w"
        ).pack(side=tk.LEFT)

        # Find current model index
        current_model = self.config.get("current_model", "")
        model_names = [m["name"] for m in self.models]
        current_index = 0
        for i, m in enumerate(self.models):
            if m["endpoint"] == current_model:
                current_index = i
                break

        self.model_var = tk.StringVar(value=model_names[current_index] if model_names else "Loading...")
        self.model_combo = ttk.Combobox(
            model_row,
            textvariable=self.model_var,
            values=model_names,
            state="readonly",
            font=("Segoe UI", 10),
            width=28
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
            command=self._refresh_models
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=2)

        # Duration label
        duration = self.models[current_index]["duration"] if self.models else 10
        self.duration_label = tk.Label(
            model_row,
            text=f"Duration: {duration}s",
            font=("Segoe UI", 9),
            bg=COLORS["bg_input"],
            fg=COLORS["accent_blue"]
        )
        self.duration_label.pack(side=tk.LEFT, padx=5)

        # Model count and status
        self.model_status = tk.Label(
            model_row,
            text=f"({len(self.models)} models)",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"]
        )
        self.model_status.pack(side=tk.LEFT, padx=5)

        # Row 3: Browse models link
        link_row = tk.Frame(controls_frame, bg=COLORS["bg_input"])
        link_row.pack(fill=tk.X)

        tk.Label(
            link_row,
            text="",
            bg=COLORS["bg_input"],
            width=12
        ).pack(side=tk.LEFT)

        browse_link = tk.Label(
            link_row,
            text="📋 Browse all models on fal.ai →",
            font=("Segoe UI", 9, "underline"),
            bg=COLORS["bg_input"],
            fg=COLORS["accent_blue"],
            cursor="hand2"
        )
        browse_link.pack(side=tk.LEFT, padx=5)
        browse_link.bind("<Button-1>", lambda e: os.startfile(FAL_MODELS_URL) if os.name == 'nt' else None)

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
            anchor="w"
        ).pack(side=tk.LEFT)

        self.custom_endpoint_var = tk.StringVar(value="")
        self.custom_entry = tk.Entry(
            custom_row,
            textvariable=self.custom_endpoint_var,
            font=("Consolas", 9),
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            width=40
        )
        self.custom_entry.pack(side=tk.LEFT, padx=5)

        # Placeholder text
        self.custom_entry.insert(0, "fal-ai/kling-video/v2.5/pro/image-to-video")
        self.custom_entry.config(fg=COLORS["text_dim"])

        def on_custom_focus_in(e):
            if self.custom_entry.get() == "fal-ai/kling-video/v2.5/pro/image-to-video":
                self.custom_entry.delete(0, tk.END)
                self.custom_entry.config(fg=COLORS["text_light"])

        def on_custom_focus_out(e):
            if not self.custom_entry.get().strip():
                self.custom_entry.insert(0, "fal-ai/kling-video/v2.5/pro/image-to-video")
                self.custom_entry.config(fg=COLORS["text_dim"])

        self.custom_entry.bind("<FocusIn>", on_custom_focus_in)
        self.custom_entry.bind("<FocusOut>", on_custom_focus_out)

        self.use_custom_btn = tk.Button(
            custom_row,
            text="Use Custom",
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            command=self._use_custom_endpoint
        )
        self.use_custom_btn.pack(side=tk.LEFT, padx=5)

        # Custom endpoint status
        self.custom_status = tk.Label(
            custom_row,
            text="",
            font=("Segoe UI", 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_dim"]
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
            fg=COLORS["text_light"]
        )
        self.prompt_label.pack(side=tk.LEFT)

        # Character count
        self.char_count = tk.Label(
            prompt_label_frame,
            text="0 chars",
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"]
        )
        self.char_count.pack(side=tk.RIGHT)

        # Text area with scrollbar
        text_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

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
            pady=10
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text.yview)

        # Bind text changes for character count
        self.text.bind("<KeyRelease>", self._update_char_count)

        # Load initial prompt for current slot
        self._load_prompt_for_slot(self.slot_var.get())

        # Button frame
        btn_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        # Info label
        tk.Label(
            btn_frame,
            text="💾 Changes are saved to kling_config.json",
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"]
        ).pack(side=tk.LEFT)

        # Cancel button
        tk.Button(
            btn_frame,
            text="✖ Cancel",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=12,
            command=self._cancel
        ).pack(side=tk.RIGHT, padx=5)

        # Save button
        tk.Button(
            btn_frame,
            text="💾 Save",
            font=("Segoe UI", 10, "bold"),
            bg="#329632",
            fg="white",
            width=12,
            command=self._save
        ).pack(side=tk.RIGHT, padx=5)

    def _on_slot_changed(self):
        """Handle slot selection change - save current and load new slot's prompt."""
        # Save current slot's text before switching
        current_text = self.text.get("1.0", tk.END).strip()
        self.saved_prompts[str(self.current_slot)] = current_text

        # Switch to new slot
        new_slot = self.slot_var.get()
        self.current_slot = new_slot
        self.prompt_label.config(text=f"Prompt for Slot {new_slot}:")
        self._load_prompt_for_slot(new_slot)

    def _load_prompt_for_slot(self, slot: int):
        """Load prompt text for the specified slot."""
        prompt = self.saved_prompts.get(str(slot), "") or ""
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", prompt)
        self._update_char_count()

    def _on_model_changed(self, event=None):
        """Handle model selection change."""
        model_name = self.model_var.get()
        for m in self.models:
            if m["name"] == model_name:
                self.duration_label.config(text=f"Duration: {m['duration']}s")
                # Clear custom status when selecting from dropdown
                self.custom_status.config(text="", fg=COLORS["text_dim"])
                break

    def _use_custom_endpoint(self):
        """Use the custom endpoint from the entry field."""
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
        existing = next((m for m in self.models if m["endpoint"] == custom_endpoint), None)
        if not existing:
            custom_model = {
                "name": f"[Custom] {display_name}",
                "endpoint": custom_endpoint,
                "duration": 10,  # Default duration
                "description": "Custom endpoint"
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
                self.duration_label.config(text=f"Duration: {m['duration']}s")
                break

        self.custom_status.config(text="✓ Custom model set", fg="#64FF64")

    def _refresh_models(self):
        """Fetch fresh model list from fal.ai API."""
        if self.is_loading_models:
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

    def _update_models(self, models: list, error: str):
        """Update model dropdown with fetched models."""
        # Safety check: dialog may have been closed before callback fired
        if not self.winfo_exists():
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
        self.duration_label.config(text=f"Duration: {models[new_index]['duration']}s")
        self.model_status.config(text=f"({len(models)} models)", fg="#64FF64")

    def _update_char_count(self, event=None):
        """Update character count label."""
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
        # Save current slot's text to local dict
        current_text = self.text.get("1.0", tk.END).strip()
        self.saved_prompts[str(self.current_slot)] = current_text

        model = self._get_selected_model()
        self.result = {
            "slot": self.slot_var.get(),
            "prompt": current_text,
            "model_name": model["name"],
            "model_endpoint": model["endpoint"],
            "duration": model["duration"],
            "all_prompts": self.saved_prompts.copy()  # Include all edited prompts
        }
        self.destroy()

    def _cancel(self):
        """Cancel and close."""
        self.result = None
        self.destroy()
