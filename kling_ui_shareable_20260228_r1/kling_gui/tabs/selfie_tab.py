"""Selfie Tab — Generate selfie-style portraits using FLUX PuLID."""

import tkinter as tk
from tkinter import ttk, filedialog
import threading
import os
import shutil
import platform
import subprocess
from typing import Callable

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession

try:
    from selfie_prompt_composer import DEFAULT_GENDER, DEFAULT_CAMERA_STYLE
except Exception:
    DEFAULT_GENDER = "female"
    DEFAULT_CAMERA_STYLE = "phone_selfie"


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
        self._last_result_path = ""

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
            value=self.config.get("composer_gender", DEFAULT_GENDER)
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
            value=self.config.get("composer_camera_style", DEFAULT_CAMERA_STYLE)
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

        # Face Resemblance (ID Weight)
        tk.Label(
            grid,
            text="Face Resemblance:",
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
        id_scale.grid(row=0, column=1, columnspan=3, padx=5, pady=2, sticky="w")

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
        ).grid(row=1, column=0, sticky="w")

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
        aspect_combo.grid(row=1, column=1, columnspan=3, padx=5, pady=2, sticky="w")

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

        # Save location settings
        save_frame = tk.LabelFrame(
            self,
            text="Save Location",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        save_frame.pack(fill=tk.X, padx=10, pady=5)

        save_mode = self.config.get("selfie_output_mode", "")
        if save_mode not in ("source", "custom"):
            save_mode = "source" if self.config.get("use_source_folder", True) else "custom"
        self.output_mode_var = tk.StringVar(value=save_mode)
        self.output_path_var = tk.StringVar(
            value=self.config.get("selfie_output_folder", self.config.get("output_folder", ""))
        )

        mode_row = tk.Frame(save_frame, bg=COLORS["bg_panel"])
        mode_row.pack(fill=tk.X, padx=5, pady=(4, 2))
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
        path_row.pack(fill=tk.X, padx=5, pady=(0, 5))
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
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", text)

    def _get_selected_dimensions(self) -> tuple:
        """Return (width, height) for the currently selected aspect ratio."""
        return self._aspect_ratios.get(self.aspect_var.get(), self._aspect_ratios["Portrait (3:4)"])

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
                gen = SelfieGenerator(api_key, freeimage_key=freeimage_key)
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
            self._last_result_path = result
            self.image_session.add_image(result, "selfie")
            self.log(
                f"Selfie generated: {os.path.basename(result)}", "success"
            )
            self._refresh_result_actions()
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
        }
