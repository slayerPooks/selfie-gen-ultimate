"""Selfie Tab — Generate selfie-style portraits using FLUX PuLID."""

import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os
import shutil
import platform
import subprocess
import json
import random
import re
from typing import Callable, Dict, List, Optional

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession

try:
    from selfie_prompt_composer import DEFAULT_GENDER
except Exception:
    DEFAULT_GENDER = "female"


class SelfieTab(tk.Frame):
    """Tab 2: Generate selfie from identity reference."""

    DEFAULT_PROMPT_TEMPLATE = (
        "A raw, unedited iPhone 7 front-camera selfie of a {age_range} {gender} \n"
        "wearing {clothing}. {expression} expression. Hair is {hair}. Skin is {skin}. \n"
        "Eyes are {eyes}. Face is {face_shape}. Phone held at arm's length, slightly \n"
        "off-center, natural edge distortion from extended arm. Background is {scene}. \n"
        "Warm practical indoor lighting. Amateur photography aesthetic, unfiltered \n"
        "iPhone 7 quality."
    )
    DEFAULT_SCENE_TEMPLATES = [
        "sunny park, green trees bokeh background",
        "cozy kitchen, warm overhead light",
        "living room, TV glow",
        "cafe, soft window light",
        "outdoor street, urban daylight",
    ]
    DEFAULT_WILDCARD_TEMPLATE = (
        "A raw, unedited iPhone 7 front-camera selfie of a {young adult|middle-aged} "
        "{woman|man} wearing a {black|gray|white|maroon|navy} "
        "{hoodie|t-shirt|sweater|jacket|blouse}. "
        "{Neutral|Slight smile|Relaxed|Confident} expression. "
        "Phone held at arm's length, slightly off-center, natural edge distortion. "
        "Background is {sunny park with green trees|cozy kitchen with warm light|"
        "living room with TV glow|outdoor street in urban daylight|"
        "cafe with soft window light}. "
        "Warm practical lighting. Amateur photography aesthetic, unfiltered iPhone 7 quality."
    )
    DISABLED_BY_DEFAULT_ENDPOINTS = {
        "fal-ai/bytedance/seedream/v5/edit",
    }

    def __init__(
        self,
        parent,
        image_session: ImageSession,
        config: dict,
        config_getter: Callable[[], dict],
        log_callback: Callable[[str, str], None],
        **kwargs,
    ):
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.image_session = image_session
        self.config = config
        self.get_config = config_getter
        self.log = log_callback
        self._busy = False
        self._last_result_path = ""
        self._model_options = self._load_model_options()
        self._model_vars: Dict[str, tk.BooleanVar] = {}
        self._handoff_identity_data: Optional[Dict[str, str]] = None
        self._handoff_scene: Optional[str] = None
        self._scene_roll_counter = 0
        self._prompt_template_edit_mode = False
        self._prompt_mode_var = tk.StringVar(
            value=config.get("selfie_prompt_mode", "json_handoff")
        )

        self._build_ui()

    def _build_ui(self):
        # Pack btn_frame FIRST so it always reserves its bottom strip,
        # even when content_frame overflows vertically.
        btn_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)
        self._btn_frame = btn_frame  # buttons added at end of method

        content_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Prompt section (uses composed prompt or custom)
        prompt_frame = tk.LabelFrame(
            content_frame,
            text="Selfie Prompt",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            labelanchor="nw",
        )
        prompt_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        # Prompt mode toggle
        mode_row = tk.Frame(prompt_frame, bg=COLORS["bg_panel"])
        mode_row.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Label(
            mode_row,
            text="Mode:",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Radiobutton(
            mode_row,
            text="JSON Handoff (Vision)",
            variable=self._prompt_mode_var,
            value="json_handoff",
            command=self._on_prompt_mode_changed,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_input"],
            activebackground=COLORS["bg_panel"],
            font=(FONT_FAMILY, 9),
        ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Radiobutton(
            mode_row,
            text="Dynamic Wildcards",
            variable=self._prompt_mode_var,
            value="wildcards",
            command=self._on_prompt_mode_changed,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_input"],
            activebackground=COLORS["bg_panel"],
            font=(FONT_FAMILY, 9),
        ).pack(side=tk.LEFT)

        # Hidden variables for composer (gender extracted from JSON, style defaults to candid)
        self._composer_frame = tk.Frame(prompt_frame, bg=COLORS["bg_panel"])
        # Not packed — Subject/Style/Compose row removed; gender comes from JSON handoff
        self.gender_var = tk.StringVar(
            value=self.config.get("composer_gender", DEFAULT_GENDER)
        )
        self.style_var = tk.StringVar(
            value=self.config.get("composer_camera_style", "candid")
        )

        # Prompt text + randomize scene (JSON Handoff mode)
        self._prompt_editor_frame = tk.Frame(prompt_frame, bg=COLORS["bg_panel"])
        self._prompt_editor_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        prompt_editor_frame = self._prompt_editor_frame

        self.prompt_text = tk.Text(
            prompt_editor_frame,
            height=5,
            wrap=tk.WORD,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            insertbackground=COLORS["text_light"],
            padx=5,
            pady=4,
        )
        self.prompt_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.prompt_text.insert("1.0", "")
        self.randomize_scene_btn = tk.Button(
            prompt_editor_frame,
            text="Randomize Scene",
            font=(FONT_FAMILY, 8),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_randomize_scene,
            cursor="hand2",
            relief=tk.FLAT,
            padx=8,
            pady=2,
        )
        self.randomize_scene_btn.pack(side=tk.LEFT, padx=(6, 0), anchor="n")

        self._templates_row = tk.Frame(prompt_frame, bg=COLORS["bg_panel"])
        self._templates_row.pack(fill=tk.X, padx=4, pady=(0, 4))
        templates_row = self._templates_row

        scene_templates_frame = tk.LabelFrame(
            templates_row,
            text="Scene Templates (One Per Line)",
            font=(FONT_FAMILY, 8, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        scene_templates_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))
        self.scene_templates_text = tk.Text(
            scene_templates_frame,
            height=3,
            wrap=tk.WORD,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            insertbackground=COLORS["text_light"],
            padx=5,
            pady=4,
        )
        self.scene_templates_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        saved_scene_templates = self.config.get(
            "selfie_scene_templates", self.DEFAULT_SCENE_TEMPLATES
        )
        if not isinstance(saved_scene_templates, list):
            saved_scene_templates = list(self.DEFAULT_SCENE_TEMPLATES)
        scene_templates = [
            str(item).strip()
            for item in saved_scene_templates
            if str(item).strip()
        ]
        if not scene_templates:
            scene_templates = list(self.DEFAULT_SCENE_TEMPLATES)
        self.scene_templates_text.insert("1.0", "\n".join(scene_templates))

        template_frame = tk.LabelFrame(
            templates_row,
            text="Prompt Template (JSON Handoff)",
            font=(FONT_FAMILY, 8, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        template_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3, 0))
        self.prompt_template_text = tk.Text(
            template_frame,
            height=5,
            wrap=tk.WORD,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            insertbackground=COLORS["text_light"],
            padx=5,
            pady=4,
        )
        self.prompt_template_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))
        saved_template = self.config.get(
            "selfie_prompt_template", self.DEFAULT_PROMPT_TEMPLATE
        )
        self.prompt_template_text.insert(
            "1.0", (saved_template or self.DEFAULT_PROMPT_TEMPLATE).strip()
        )
        self.prompt_template_text.config(state=tk.DISABLED)

        template_actions = tk.Frame(template_frame, bg=COLORS["bg_panel"])
        template_actions.pack(fill=tk.X, padx=4, pady=(0, 3))
        self.edit_template_btn = tk.Button(
            template_actions,
            text="Edit Template",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._on_edit_prompt_template,
            cursor="hand2",
            relief=tk.FLAT,
            padx=7,
            pady=1,
        )
        self.edit_template_btn.pack(side=tk.LEFT)
        self.save_template_btn = tk.Button(
            template_actions,
            text="Save Template",
            font=(FONT_FAMILY, 8),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_save_prompt_template,
            cursor="hand2",
            relief=tk.FLAT,
            padx=7,
            pady=1,
            state=tk.DISABLED,
        )
        self.save_template_btn.pack(side=tk.LEFT, padx=(5, 0))
        self.reset_template_btn = tk.Button(
            template_actions,
            text="Reset Template",
            font=(FONT_FAMILY, 8),
            bg=COLORS["btn_red"],
            fg="white",
            command=self._on_reset_prompt_template,
            cursor="hand2",
            relief=tk.FLAT,
            padx=7,
            pady=1,
        )
        self.reset_template_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Wildcard template (Dynamic Wildcards mode — hidden by default)
        self._wildcard_frame = tk.LabelFrame(
            prompt_frame,
            text="Wildcard Template  {option1|option2|option3}",
            font=(FONT_FAMILY, 8, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        # Don't pack yet — managed by _apply_prompt_mode_ui()

        self._wildcard_text = tk.Text(
            self._wildcard_frame,
            height=7,
            wrap=tk.WORD,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            insertbackground=COLORS["text_light"],
            padx=5,
            pady=4,
        )
        self._wildcard_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))

        saved_wildcard = self.config.get(
            "selfie_wildcard_template", self.DEFAULT_WILDCARD_TEMPLATE
        )
        self._wildcard_text.insert("1.0", (saved_wildcard or self.DEFAULT_WILDCARD_TEMPLATE).strip())
        self._wildcard_text.config(state=tk.DISABLED)

        wildcard_actions = tk.Frame(self._wildcard_frame, bg=COLORS["bg_panel"])
        wildcard_actions.pack(fill=tk.X, padx=4, pady=(0, 3))
        self._edit_wildcard_btn = tk.Button(
            wildcard_actions,
            text="Edit Template",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._on_edit_wildcard_template,
            cursor="hand2",
            relief=tk.FLAT,
            padx=7,
            pady=1,
        )
        self._edit_wildcard_btn.pack(side=tk.LEFT)
        self._save_wildcard_btn = tk.Button(
            wildcard_actions,
            text="Save Template",
            font=(FONT_FAMILY, 8),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_save_wildcard_template,
            cursor="hand2",
            relief=tk.FLAT,
            padx=7,
            pady=1,
            state=tk.DISABLED,
        )
        self._save_wildcard_btn.pack(side=tk.LEFT, padx=(5, 0))
        tk.Button(
            wildcard_actions,
            text="Reset Template",
            font=(FONT_FAMILY, 8),
            bg=COLORS["btn_red"],
            fg="white",
            command=self._on_reset_wildcard_template,
            cursor="hand2",
            relief=tk.FLAT,
            padx=7,
            pady=1,
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Apply initial prompt mode visibility
        self._apply_prompt_mode_ui()

        # Settings
        settings_frame = tk.LabelFrame(
            content_frame,
            text="Generation Settings",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        settings_frame.pack(fill=tk.X, padx=8, pady=4)

        grid = tk.Frame(settings_frame, bg=COLORS["bg_panel"])
        grid.pack(fill=tk.X, padx=4, pady=4)

        # Face Resemblance (ID Weight)
        tk.Label(
            grid,
            text="Face Resemblance:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=0, column=0, sticky="w")
        self.id_weight_var = tk.DoubleVar(
            value=self.config.get("selfie_id_weight", 1.0)
        )
        id_scale = tk.Scale(
            grid,
            from_=0.0,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            variable=self.id_weight_var,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            troughcolor=COLORS["bg_input"],
            highlightthickness=0,
            length=150,
        )
        id_scale.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        # Aspect Ratio (replaces manual Width/Height)
        self._aspect_ratios = {
            "Portrait (3:4)": (896, 1152),
            "Landscape (16:9)": (1280, 720),
            "Square (1:1)": (1024, 1024),
        }
        tk.Label(
            grid,
            text="Aspect Ratio:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))

        # Determine saved selection from config dimensions
        default_ratio_name = "Portrait (3:4)"
        default_w, default_h = self._aspect_ratios[default_ratio_name]
        try:
            saved_w = int(self.config.get("selfie_width", default_w))
            saved_h = int(self.config.get("selfie_height", default_h))
        except (TypeError, ValueError):
            saved_w, saved_h = default_w, default_h
        dims_to_name = {dims: name for name, dims in self._aspect_ratios.items()}
        saved_ratio = dims_to_name.get((saved_w, saved_h))
        if not saved_ratio:
            custom_ratio = f"Custom ({saved_w}x{saved_h})"
            self._aspect_ratios[custom_ratio] = (saved_w, saved_h)
            saved_ratio = custom_ratio
        self.aspect_var = tk.StringVar(value=saved_ratio)
        aspect_combo = ttk.Combobox(
            grid,
            textvariable=self.aspect_var,
            values=list(self._aspect_ratios.keys()),
            state="readonly",
            width=18,
        )
        aspect_combo.grid(row=0, column=3, padx=5, pady=2, sticky="w")

        # Seed
        tk.Label(
            grid,
            text="Seed:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=1, column=0, sticky="w")
        self.seed_var = tk.IntVar(value=self.config.get("selfie_seed", -1))
        tk.Entry(
            grid,
            textvariable=self.seed_var,
            width=10,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        self.random_seed_var = tk.BooleanVar(
            value=self.config.get("selfie_random_seed", True)
        )
        tk.Checkbutton(
            grid,
            text="Random",
            variable=self.random_seed_var,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_input"],
            activebackground=COLORS["bg_panel"],
            font=(FONT_FAMILY, 9),
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=(12, 0))

        # Model selection
        models_frame = tk.LabelFrame(
            content_frame,
            text="Step 2 Models",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        models_frame.pack(fill=tk.X, padx=8, pady=4)

        models_list_container = tk.Frame(models_frame, bg=COLORS["bg_panel"])
        models_list_container.pack(fill=tk.X, padx=4, pady=3)
        models_canvas = tk.Canvas(
            models_list_container,
            bg=COLORS["bg_panel"],
            highlightthickness=0,
            borderwidth=0,
            height=140,
        )
        models_scroll = ttk.Scrollbar(
            models_list_container,
            orient=tk.VERTICAL,
            command=models_canvas.yview,
        )
        models_canvas.configure(yscrollcommand=models_scroll.set)
        models_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        models_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        models_grid_frame = tk.Frame(models_canvas, bg=COLORS["bg_panel"])
        models_grid_frame.grid_columnconfigure(0, weight=1)
        models_grid_frame.grid_columnconfigure(1, weight=1)
        models_window_id = models_canvas.create_window(
            (0, 0),
            window=models_grid_frame,
            anchor="nw",
        )

        def _on_models_grid_configure(_event):
            models_canvas.configure(scrollregion=models_canvas.bbox("all"))

        def _on_models_canvas_configure(event):
            models_canvas.itemconfigure(models_window_id, width=event.width)

        models_grid_frame.bind("<Configure>", _on_models_grid_configure)
        models_canvas.bind("<Configure>", _on_models_canvas_configure)

        saved_models = self.config.get("selfie_selected_models", {})
        for idx, model in enumerate(self._model_options):
            endpoint = model.get("endpoint", "")
            label = model.get("label", endpoint)
            default_checked = (
                endpoint == "fal-ai/flux-pulid"
                and endpoint not in self.DISABLED_BY_DEFAULT_ENDPOINTS
            )
            checked = bool(saved_models.get(endpoint, default_checked))
            var = tk.BooleanVar(value=checked)
            self._model_vars[endpoint] = var
            tk.Checkbutton(
                models_grid_frame,
                text=label,
                variable=var,
                bg=COLORS["bg_panel"],
                fg=COLORS["text_light"],
                selectcolor=COLORS["bg_input"],
                activebackground=COLORS["bg_panel"],
                font=(FONT_FAMILY, 8),
                anchor="w",
            ).grid(
                row=idx // 2,
                column=idx % 2,
                sticky="w",
                padx=(8, 20),
                pady=0,
            )

        # Save location settings
        save_frame = tk.LabelFrame(
            content_frame,
            text="Save Location",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        save_frame.pack(fill=tk.X, padx=8, pady=4)

        save_mode = self.config.get("selfie_output_mode", "")
        if save_mode not in ("source", "custom"):
            save_mode = "source" if self.config.get("use_source_folder", True) else "custom"
        self.output_mode_var = tk.StringVar(value=save_mode)
        self.output_path_var = tk.StringVar(
            value=self.config.get("selfie_output_folder", self.config.get("output_folder", ""))
        )

        mode_row = tk.Frame(save_frame, bg=COLORS["bg_panel"])
        mode_row.pack(fill=tk.X, padx=4, pady=(3, 1))
        tk.Radiobutton(
            mode_row,
            text="Save Next To Source Image",
            variable=self.output_mode_var,
            value="source",
            command=self._on_output_mode_changed,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_input"],
            activebackground=COLORS["bg_panel"],
            font=(FONT_FAMILY, 9),
        ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Radiobutton(
            mode_row,
            text="Save In Custom Folder",
            variable=self.output_mode_var,
            value="custom",
            command=self._on_output_mode_changed,
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            selectcolor=COLORS["bg_input"],
            activebackground=COLORS["bg_panel"],
            font=(FONT_FAMILY, 9),
        ).pack(side=tk.LEFT)

        path_row = tk.Frame(save_frame, bg=COLORS["bg_panel"])
        path_row.pack(fill=tk.X, padx=4, pady=(0, 3))
        self.output_entry = tk.Entry(
            path_row,
            textvariable=self.output_path_var,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            relief=tk.FLAT,
        )
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.browse_btn = tk.Button(
            path_row,
            text="Browse",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._browse_output_folder,
            cursor="hand2",
            relief=tk.FLAT,
            padx=10,
        )
        self.browse_btn.pack(side=tk.LEFT)
        self._update_output_entry_state()

        # Action buttons (btn_frame was packed at top of _build_ui)
        btn_frame = self._btn_frame

        self.generate_btn = tk.Button(
            btn_frame,
            text="Generate Selfie",
            font=(FONT_FAMILY, 11, "bold"),
            bg=COLORS["btn_green"],
            fg="white",
            command=self._on_generate,
            cursor="hand2",
            relief=tk.FLAT,
            padx=20,
            pady=6,
        )
        self.generate_btn.pack(side=tk.LEFT)

        self.save_as_btn = tk.Button(
            btn_frame,
            text="Save As...",
            font=(FONT_FAMILY, 9),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_save_as,
            cursor="hand2",
            relief=tk.FLAT,
            padx=10,
            state=tk.DISABLED,
        )
        self.save_as_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.open_file_btn = tk.Button(
            btn_frame,
            text="Open Image",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._on_open_result_file,
            cursor="hand2",
            relief=tk.FLAT,
            padx=10,
            state=tk.DISABLED,
        )
        self.open_file_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.open_folder_btn = tk.Button(
            btn_frame,
            text="Open Folder",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._on_open_result_folder,
            cursor="hand2",
            relief=tk.FLAT,
            padx=10,
            state=tk.DISABLED,
        )
        self.open_folder_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.status_label = tk.Label(
            btn_frame,
            text="",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

    def set_prompt(self, text: str):
        """Set the prompt text (called by Step 1 'Send to Step 2')."""
        raw_text = (text or "").strip()
        if not raw_text:
            self._handoff_identity_data = None
            self.prompt_text.delete("1.0", tk.END)
            return

        payload = self._extract_handoff_json(raw_text)

        normalized = None
        if payload is not None:
            try:
                from selfie_generator import SelfieGenerator
                normalized = SelfieGenerator.normalize_handoff_identity(payload)
            except Exception:
                normalized = None

        if normalized:
            self._handoff_identity_data = normalized
            self._handoff_scene = None
            self._scene_roll_counter = 0
            self._apply_handoff_scene_prompt(reroll=False)
            self.prompt_text.delete("1.0", tk.END)
            self.prompt_text.insert("1.0", json.dumps(normalized, indent=2))
            return

        self._handoff_identity_data = None
        self._handoff_scene = None
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", text)

    def _extract_handoff_json(self, raw_text: str) -> Optional[dict]:
        """Parse JSON payload even when Step 1 sends wrapper text around it."""
        if not raw_text:
            return None

        candidates = [raw_text]
        first_brace = raw_text.find("{")
        last_brace = raw_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidates.append(raw_text[first_brace : last_brace + 1])

        for candidate in candidates:
            try:
                payload = json.loads(candidate.strip())
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue
        return None

    def _get_selected_dimensions(self) -> tuple:
        """Return (width, height) for the currently selected aspect ratio."""
        return self._aspect_ratios.get(self.aspect_var.get(), self._aspect_ratios["Portrait (3:4)"])

    def _get_scene_templates(self) -> List[str]:
        if not hasattr(self, "scene_templates_text"):
            return list(self.DEFAULT_SCENE_TEMPLATES)
        lines = self.scene_templates_text.get("1.0", tk.END).splitlines()
        templates = [line.strip() for line in lines if line.strip()]
        return templates or list(self.DEFAULT_SCENE_TEMPLATES)

    def _get_prompt_template_text(self) -> str:
        if not hasattr(self, "prompt_template_text"):
            return self.DEFAULT_PROMPT_TEMPLATE
        text = self.prompt_template_text.get("1.0", tk.END).strip()
        return text if text else self.DEFAULT_PROMPT_TEMPLATE

    def _set_prompt_template_edit_mode(self, enabled: bool):
        self._prompt_template_edit_mode = enabled
        self.prompt_template_text.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self.edit_template_btn.config(state=tk.DISABLED if enabled else tk.NORMAL)
        self.save_template_btn.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def _on_edit_prompt_template(self):
        self._set_prompt_template_edit_mode(True)
        self.prompt_template_text.focus_set()
        self.prompt_template_text.mark_set(tk.INSERT, tk.END)

    def _on_save_prompt_template(self):
        text = self._get_prompt_template_text()
        self.prompt_template_text.config(state=tk.NORMAL)
        self.prompt_template_text.delete("1.0", tk.END)
        self.prompt_template_text.insert("1.0", text)
        self._set_prompt_template_edit_mode(False)
        self.log("Selfie prompt template saved", "success")

    def _on_reset_prompt_template(self):
        self.prompt_template_text.config(state=tk.NORMAL)
        self.prompt_template_text.delete("1.0", tk.END)
        self.prompt_template_text.insert("1.0", self.DEFAULT_PROMPT_TEMPLATE)
        self._set_prompt_template_edit_mode(False)
        self.log("Selfie prompt template reset to default", "info")

    def _on_prompt_mode_changed(self):
        self._apply_prompt_mode_ui()
        mode_label = "JSON Handoff" if self._prompt_mode_var.get() == "json_handoff" else "Dynamic Wildcards"
        self.log(f"Prompt mode: {mode_label}", "info")

    def _apply_prompt_mode_ui(self):
        """Show/hide widgets based on the active prompt mode."""
        if self._prompt_mode_var.get() == "wildcards":
            self._composer_frame.pack_forget()
            self._prompt_editor_frame.pack_forget()
            self._templates_row.pack_forget()
            self._wildcard_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        else:
            self._wildcard_frame.pack_forget()
            self._composer_frame.pack(fill=tk.X, padx=4, pady=4)
            self._prompt_editor_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
            self._templates_row.pack(fill=tk.X, padx=4, pady=(0, 4))

    def _set_wildcard_edit_mode(self, enabled: bool):
        self._wildcard_text.config(state=tk.NORMAL if enabled else tk.DISABLED)
        self._edit_wildcard_btn.config(state=tk.DISABLED if enabled else tk.NORMAL)
        self._save_wildcard_btn.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def _on_edit_wildcard_template(self):
        self._set_wildcard_edit_mode(True)
        self._wildcard_text.focus_set()
        self._wildcard_text.mark_set(tk.INSERT, tk.END)

    def _on_save_wildcard_template(self):
        text = self._wildcard_text.get("1.0", tk.END).strip()
        if not text:
            text = self.DEFAULT_WILDCARD_TEMPLATE
        self._wildcard_text.config(state=tk.NORMAL)
        self._wildcard_text.delete("1.0", tk.END)
        self._wildcard_text.insert("1.0", text)
        self._set_wildcard_edit_mode(False)
        self.log("Wildcard template saved", "success")

    def _on_reset_wildcard_template(self):
        self._wildcard_text.config(state=tk.NORMAL)
        self._wildcard_text.delete("1.0", tk.END)
        self._wildcard_text.insert("1.0", self.DEFAULT_WILDCARD_TEMPLATE)
        self._set_wildcard_edit_mode(False)
        self.log("Wildcard template reset to default", "info")

    def _apply_handoff_scene_prompt(self, reroll: bool):
        if not self._handoff_identity_data:
            return
        if reroll:
            self._scene_roll_counter += 1

        scene_templates = self._get_scene_templates()
        if not scene_templates:
            self.log("Scene template list is empty", "warning")
            return

        try:
            seed_value = int(self.seed_var.get())
        except (tk.TclError, TypeError, ValueError):
            seed_value = 0
        rng = random.Random(seed_value + self._scene_roll_counter)
        self._handoff_scene = rng.choice(scene_templates)

    def _build_handoff_prompt(self) -> str:
        if not self._handoff_identity_data:
            return ""
        if not self._handoff_scene:
            self._apply_handoff_scene_prompt(reroll=False)
        scene = self._handoff_scene or self.DEFAULT_SCENE_TEMPLATES[0]
        return self._get_prompt_template_text().format(
            scene=scene,
            **self._handoff_identity_data,
        )

    def _on_randomize_scene(self):
        if not self._handoff_identity_data:
            self.log("No Step 1 JSON prompt to randomize yet", "warning")
            return
        self._apply_handoff_scene_prompt(reroll=True)
        self.log("Scene randomized for JSON handoff", "info")

    def _compose_prompt(self):
        """Compose prompt from selected options."""
        try:
            from selfie_prompt_composer import SelfiePromptComposer

            composer = SelfiePromptComposer()
            prompt = composer.compose(
                gender=self.gender_var.get(),
                camera_style=self.style_var.get(),
            )
            self._handoff_identity_data = None
            self._scene_roll_counter = 0
            self.prompt_text.delete("1.0", tk.END)
            self.prompt_text.insert("1.0", prompt)
        except ImportError:
            self.log("selfie_prompt_composer module not found", "error")
        except Exception as e:
            self.log(f"Compose error: {e}", "error")

    def _on_generate(self):
        if self._busy:
            return

        config = self.get_config()
        api_key = config.get("falai_api_key", "")
        bfl_api_key = config.get("bfl_api_key", "")

        image_path = self.image_session.active_image_path
        if not image_path:
            self.log("No image selected in carousel", "warning")
            return

        mode = self._prompt_mode_var.get()
        wildcard_template = None
        if mode == "wildcards":
            raw = self._wildcard_text.get("1.0", tk.END).strip()
            if not raw:
                self.log("Wildcard template is empty", "warning")
                return
            # Save raw template — wildcards will be resolved per-model in _run()
            wildcard_template = raw
            prompt = raw  # placeholder; each model gets a fresh resolution
        elif self._handoff_identity_data:
            prompt = self._build_handoff_prompt().strip()
            if not prompt:
                self.log("Prompt template is empty", "warning")
                return
        else:
            prompt = self.prompt_text.get("1.0", tk.END).strip()
            if not prompt:
                self.log("Prompt is empty", "warning")
                return

        selected_models = self._get_selected_models()
        if not selected_models:
            self.log("Select at least one Step 2 model", "warning")
            return

        # Validate API keys per provider
        needs_fal = any(m.get("provider", "fal") == "fal" for m in selected_models)
        needs_bfl = any(m.get("provider") == "bfl" for m in selected_models)
        if needs_fal and not api_key:
            self.log("fal.ai API key required for selected fal.ai models", "error")
            return
        if needs_bfl and not bfl_api_key:
            self.log("BFL API key required for selected BFL models", "error")
            return

        try:
            output_folder = self._resolve_output_folder(image_path)
        except Exception as e:
            self.log(f"Invalid output folder: {e}", "error")
            return

        # Read numeric vars BEFORE setting busy — .get() raises TclError
        # if the entry contains non-numeric text.
        try:
            seed = -1 if self.random_seed_var.get() else self.seed_var.get()
            id_weight = self.id_weight_var.get()
            width, height = self._get_selected_dimensions()
        except (tk.TclError, ValueError):
            self.log("Invalid numeric value in settings", "error")
            return

        self._set_busy(True)

        def _run():
            try:
                from selfie_generator import SelfieGenerator

                freeimage_key = self.get_config().get("freeimage_api_key")
                gen = SelfieGenerator(api_key, freeimage_key=freeimage_key, bfl_api_key=bfl_api_key)
                gen.set_progress_callback(
                    lambda msg, lvl: self.winfo_toplevel().after(
                        0, lambda m=msg, l=lvl: self.log(m, l)
                    )
                )
                results = []
                failed_models = []

                for model in selected_models:
                    endpoint = model.get("endpoint", "")
                    label = model.get("label", endpoint)

                    # Resolve wildcards per-model for variety
                    if wildcard_template:
                        model_prompt = SelfieGenerator.resolve_wildcards(wildcard_template)
                        self.winfo_toplevel().after(
                            0,
                            lambda l=label, p=model_prompt: self.log(
                                f"[{l}] Resolved prompt: {p[:120]}...", "debug"
                            ),
                        )
                    else:
                        model_prompt = prompt

                    self.winfo_toplevel().after(
                        0,
                        lambda l=label, e=endpoint: self.log(
                            f"Generating with {l} ({e})...", "task"
                        ),
                    )
                    result = gen.generate(
                        image_path=image_path,
                        prompt=model_prompt,
                        output_folder=output_folder,
                        id_weight=id_weight,
                        width=width,
                        height=height,
                        seed=seed,
                        model_endpoint=endpoint,
                        model_label=label,
                    )
                    if result:
                        results.append((model, result))
                        # Show result immediately in carousel
                        self.winfo_toplevel().after(
                            0,
                            lambda m=model, r=result: self._show_single_result(m, r),
                        )
                    else:
                        failed_models.append(label)

                self.winfo_toplevel().after(
                    0, lambda fl=failed_models: self._on_complete_batch(results, fl)
                )
            except Exception as e:
                err = str(e)
                self.winfo_toplevel().after(
                    0, lambda: self._on_error(err)
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_complete(self, result):
        self._set_busy(False)
        if result:
            self._last_result_path = result
            similarity = self._extract_similarity_from_result_path(result)
            selfie_label = f"Selfie (Sim: {similarity})" if similarity is not None else "Selfie (Sim: N/A)"
            self.image_session.add_image(result, "selfie", label=selfie_label)
            message = f"Selfie generated: {os.path.basename(result)}"
            if similarity is not None:
                message = f"Selfie generated (Similarity {similarity}): {os.path.basename(result)}"
            self.log(message, "success")
            self._refresh_result_actions()
        else:
            self.log("Selfie generation failed", "error")

    @staticmethod
    def _truncate_model_label(label: str) -> str:
        text = (label or "").strip()
        if not text:
            return "Model"
        return text[:18]

    @staticmethod
    def _extract_similarity_from_result_path(path: str) -> Optional[str]:
        """Extract similarity token from output filename (e.g. *_sim72_001.png)."""
        if not path:
            return None
        name = os.path.basename(path).lower()
        match = re.search(r"_sim(\d+|na)_\d{3}\.png$", name)
        if not match:
            return None
        token = match.group(1)
        return "n/a" if token == "na" else f"{token}%"

    def _format_selfie_label(self, model_label: str, result_path: str) -> str:
        short_model = self._truncate_model_label(model_label)
        similarity = self._extract_similarity_from_result_path(result_path)
        if similarity is None:
            return f"{short_model} (Sim: N/A)"
        return f"{short_model} (Sim: {similarity})"

    def _show_single_result(self, model: dict, result: str):
        """Add a single completed result to the carousel immediately."""
        label = model.get("label", model.get("endpoint", "model"))
        similarity = self._extract_similarity_from_result_path(result)
        self._last_result_path = result
        self.image_session.add_image(
            result,
            "selfie",
            label=self._format_selfie_label(label, result),
        )
        message = f"Selfie generated [{label}]: {os.path.basename(result)}"
        if similarity is not None:
            message = (
                f"Selfie generated [{label}] (Similarity {similarity}): "
                f"{os.path.basename(result)}"
            )
        self.log(message, "success")
        self._refresh_result_actions()

    def _on_complete_batch(self, results, failed_models):
        """Final summary after all models have run (results already shown progressively)."""
        self._set_busy(False)

        if not results:
            self.log("Selfie generation failed for all selected models", "error")

        total = len(results) + len(failed_models)
        if results and failed_models:
            self.log(
                f"Batch complete: {len(results)}/{total} succeeded",
                "info",
            )

        if failed_models:
            self.log(
                f"Failed models: {', '.join(failed_models)}",
                "warning",
            )

    def _on_error(self, error):
        self._set_busy(False)
        self.log(f"Error: {error}", "error")

    def _set_busy(self, busy):
        self._busy = busy
        self.generate_btn.config(
            state=tk.DISABLED if busy else tk.NORMAL,
            text="Generating..." if busy else "Generate Selfie",
        )
        if busy:
            self.save_as_btn.config(state=tk.DISABLED)
            self.open_file_btn.config(state=tk.DISABLED)
            self.open_folder_btn.config(state=tk.DISABLED)
        else:
            self._refresh_result_actions()
        self.status_label.config(
            text="Processing..." if busy else "",
            fg=COLORS["progress"] if busy else COLORS["text_dim"],
        )

    def _on_output_mode_changed(self):
        self._update_output_entry_state()
        mode_desc = (
            "next to source image"
            if self.output_mode_var.get() == "source"
            else "custom folder"
        )
        self.log(f"Selfie save mode set to {mode_desc}", "info")

    def _update_output_entry_state(self):
        use_custom = self.output_mode_var.get() == "custom"
        self.output_entry.config(state=tk.NORMAL if use_custom else tk.DISABLED)
        self.browse_btn.config(state=tk.NORMAL if use_custom else tk.DISABLED)

    def _browse_output_folder(self):
        initial_dir = self.output_path_var.get().strip() or os.path.expanduser("~")
        folder = filedialog.askdirectory(
            title="Select Selfie Output Folder",
            initialdir=initial_dir,
        )
        if folder:
            self.output_path_var.set(folder)
            self.log(f"Selfie output folder set: {folder}", "success")

    def _resolve_output_folder(self, source_image_path: str) -> str:
        if self.output_mode_var.get() == "custom":
            custom_folder = self.output_path_var.get().strip()
            if not custom_folder:
                raise ValueError("Custom output folder is empty")
            os.makedirs(custom_folder, exist_ok=True)
            return custom_folder
        source_folder = os.path.dirname(source_image_path)
        if not source_folder:
            raise ValueError("Could not resolve source image folder")
        return source_folder

    def _refresh_result_actions(self):
        has_result = bool(
            self._last_result_path and os.path.isfile(self._last_result_path)
        )
        self.save_as_btn.config(state=tk.NORMAL if has_result else tk.DISABLED)
        self.open_file_btn.config(state=tk.NORMAL if has_result else tk.DISABLED)
        self.open_folder_btn.config(state=tk.NORMAL if has_result else tk.DISABLED)

    def _open_path_in_explorer(self, path: str):
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":
                subprocess.run(["open", path], check=True)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception as e:
            self.log(f"Could not open {path}: {e}", "error")

    def _on_open_result_file(self):
        if not self._last_result_path or not os.path.isfile(self._last_result_path):
            self.log("No generated selfie file to open", "warning")
            return
        self._open_path_in_explorer(self._last_result_path)

    def _on_open_result_folder(self):
        if not self._last_result_path:
            self.log("No generated selfie folder to open", "warning")
            return
        folder = os.path.dirname(self._last_result_path)
        if not folder or not os.path.isdir(folder):
            self.log("Generated selfie folder does not exist", "warning")
            return
        self._open_path_in_explorer(folder)

    def _on_save_as(self):
        if not self._last_result_path or not os.path.isfile(self._last_result_path):
            self.log("No generated selfie to save", "warning")
            return
        initial_dir = os.path.dirname(self._last_result_path)
        initial_file = os.path.basename(self._last_result_path)
        target_path = filedialog.asksaveasfilename(
            title="Save Selfie As",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("JPEG Image", "*.jpg;*.jpeg"),
                ("WebP Image", "*.webp"),
                ("All files", "*.*"),
            ],
        )
        if not target_path:
            return
        try:
            if os.path.abspath(target_path) == os.path.abspath(self._last_result_path):
                self.log("Selected path is the same as existing generated file", "info")
                return
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(self._last_result_path, target_path)
            self.log(f"Saved copy: {target_path}", "success")
        except Exception as e:
            self.log(f"Save failed: {e}", "error")

    def _load_model_options(self) -> List[dict]:
        try:
            from selfie_generator import SelfieGenerator
            return SelfieGenerator.get_available_models()
        except Exception:
            return [
                {
                    "endpoint": "fal-ai/flux-pulid",
                    "label": "PuLID Flux",
                    "api_url": "https://fal.ai/models/fal-ai/flux-pulid/api",
                }
            ]

    def _get_selected_models(self) -> List[dict]:
        selected = []
        for model in self._model_options:
            endpoint = model.get("endpoint", "")
            var = self._model_vars.get(endpoint)
            if var and var.get():
                selected.append(model)
        return selected

    def get_config_updates(self) -> dict:
        width, height = self._get_selected_dimensions()
        return {
            "composer_gender": self.gender_var.get(),
            "composer_camera_style": self.style_var.get(),
            "selfie_id_weight": self.id_weight_var.get(),
            "selfie_width": width,
            "selfie_height": height,
            "selfie_seed": self.seed_var.get(),
            "selfie_random_seed": self.random_seed_var.get(),
            "selfie_output_mode": self.output_mode_var.get(),
            "selfie_output_folder": self.output_path_var.get().strip(),
            "selfie_scene_templates": self._get_scene_templates(),
            "selfie_prompt_template": self._get_prompt_template_text(),
            "selfie_selected_models": {
                endpoint: bool(var.get())
                for endpoint, var in self._model_vars.items()
            },
            "selfie_prompt_mode": self._prompt_mode_var.get(),
            "selfie_wildcard_template": self._wildcard_text.get("1.0", tk.END).strip(),
        }
