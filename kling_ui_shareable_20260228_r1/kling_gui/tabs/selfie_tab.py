"""Selfie Tab — Generate selfie-style portraits using FLUX PuLID."""

import tkinter as tk
from tkinter import ttk
import threading
import os
from typing import Callable

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession


class SelfieTab(tk.Frame):
    """Tab 2: Generate selfie from identity reference."""

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

        self._build_ui()

    def _build_ui(self):
        # Prompt section (uses composed prompt or custom)
        prompt_frame = tk.LabelFrame(
            self,
            text="Selfie Prompt",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
            labelanchor="nw",
        )
        prompt_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        # Composer controls
        composer_frame = tk.Frame(prompt_frame, bg=COLORS["bg_panel"])
        composer_frame.pack(fill=tk.X, padx=5, pady=5)

        # Gender
        tk.Label(
            composer_frame,
            text="Subject:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=0, column=0, sticky="w", padx=2)
        self.gender_var = tk.StringVar(
            value=self.config.get("composer_gender", "female")
        )
        gender_combo = ttk.Combobox(
            composer_frame,
            textvariable=self.gender_var,
            values=["female", "male", "neutral"],
            state="readonly",
            width=10,
        )
        gender_combo.grid(row=0, column=1, padx=5, pady=2)

        # Camera style
        tk.Label(
            composer_frame,
            text="Style:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=0, column=2, sticky="w", padx=2)
        self.style_var = tk.StringVar(
            value=self.config.get("composer_camera_style", "phone_selfie")
        )
        styles = [
            "phone_selfie",
            "mirror_selfie",
            "professional",
            "candid",
            "close_up",
        ]
        style_combo = ttk.Combobox(
            composer_frame,
            textvariable=self.style_var,
            values=styles,
            state="readonly",
            width=15,
        )
        style_combo.grid(row=0, column=3, padx=5, pady=2)

        # Compose button
        compose_btn = tk.Button(
            composer_frame,
            text="Compose",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._compose_prompt,
            cursor="hand2",
            relief=tk.FLAT,
        )
        compose_btn.grid(row=0, column=4, padx=5)

        # Prompt text
        self.prompt_text = tk.Text(
            prompt_frame,
            height=3,
            wrap=tk.WORD,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            insertbackground=COLORS["text_light"],
            padx=5,
            pady=5,
        )
        self.prompt_text.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.prompt_text.insert(
            "1.0",
            "Photo of a person, casual phone selfie, photorealistic",
        )

        # Settings
        settings_frame = tk.LabelFrame(
            self,
            text="Generation Settings",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        grid = tk.Frame(settings_frame, bg=COLORS["bg_panel"])
        grid.pack(fill=tk.X, padx=5, pady=5)

        # ID Weight
        tk.Label(
            grid,
            text="ID Weight:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=0, column=0, sticky="w")
        self.id_weight_var = tk.DoubleVar(
            value=self.config.get("selfie_id_weight", 0.8)
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
        id_scale.grid(row=0, column=1, padx=5, pady=2)

        # Dimensions
        tk.Label(
            grid,
            text="Width:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=1, column=0, sticky="w")
        self.width_var = tk.IntVar(
            value=self.config.get("selfie_width", 896)
        )
        tk.Entry(
            grid,
            textvariable=self.width_var,
            width=6,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        tk.Label(
            grid,
            text="Height:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=1, column=2, sticky="w")
        self.height_var = tk.IntVar(
            value=self.config.get("selfie_height", 1152)
        )
        tk.Entry(
            grid,
            textvariable=self.height_var,
            width=6,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=1, column=3, sticky="w", padx=5, pady=2)

        # Seed
        tk.Label(
            grid,
            text="Seed:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=2, column=0, sticky="w")
        self.seed_var = tk.IntVar(value=self.config.get("selfie_seed", -1))
        tk.Entry(
            grid,
            textvariable=self.seed_var,
            width=10,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=2, column=1, sticky="w", padx=5, pady=2)

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
        ).grid(row=2, column=2, columnspan=2, sticky="w")

        # Generate button
        btn_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

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

        self.status_label = tk.Label(
            btn_frame,
            text="",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

    def _compose_prompt(self):
        """Compose prompt from selected options."""
        try:
            from selfie_prompt_composer import SelfiePromptComposer

            composer = SelfiePromptComposer()
            prompt = composer.compose(
                gender=self.gender_var.get(),
                camera_style=self.style_var.get(),
            )
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
        if not api_key:
            self.log("fal.ai API key required (set in Video tab)", "error")
            return

        image_path = self.image_session.active_image_path
        if not image_path:
            self.log("No image selected in carousel", "warning")
            return

        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            self.log("Prompt is empty", "warning")
            return

        output_folder = config.get("output_folder", "")
        if not output_folder or not os.path.isdir(output_folder):
            output_folder = os.path.dirname(image_path)

        self._set_busy(True)
        seed = -1 if self.random_seed_var.get() else self.seed_var.get()

        id_weight = self.id_weight_var.get()
        width = self.width_var.get()
        height = self.height_var.get()

        def _run():
            try:
                from selfie_generator import SelfieGenerator

                gen = SelfieGenerator(api_key)
                gen.set_progress_callback(
                    lambda msg, lvl: self.winfo_toplevel().after(
                        0, lambda m=msg, l=lvl: self.log(m, l)
                    )
                )
                result = gen.generate(
                    image_path=image_path,
                    prompt=prompt,
                    output_folder=output_folder,
                    id_weight=id_weight,
                    width=width,
                    height=height,
                    seed=seed,
                )
                self.winfo_toplevel().after(
                    0, lambda: self._on_complete(result)
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
            self.image_session.add_image(result, "selfie")
            self.log(
                f"Selfie generated: {os.path.basename(result)}", "success"
            )
        else:
            self.log("Selfie generation failed", "error")

    def _on_error(self, error):
        self._set_busy(False)
        self.log(f"Error: {error}", "error")

    def _set_busy(self, busy):
        self._busy = busy
        self.generate_btn.config(
            state=tk.DISABLED if busy else tk.NORMAL,
            text="Generating..." if busy else "Generate Selfie",
        )
        self.status_label.config(
            text="Processing..." if busy else "",
            fg=COLORS["progress"] if busy else COLORS["text_dim"],
        )

    def get_config_updates(self) -> dict:
        return {
            "composer_gender": self.gender_var.get(),
            "composer_camera_style": self.style_var.get(),
            "selfie_id_weight": self.id_weight_var.get(),
            "selfie_width": self.width_var.get(),
            "selfie_height": self.height_var.get(),
            "selfie_seed": self.seed_var.get(),
            "selfie_random_seed": self.random_seed_var.get(),
        }
