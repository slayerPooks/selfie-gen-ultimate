"""Outpaint Tab — Expand images using fal.ai outpaint."""

import tkinter as tk
from tkinter import ttk
import threading
import os
from typing import Callable

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession


class OutpaintTab(tk.Frame):
    """Tab 3: Expand (outpaint) images."""

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
        # Expansion settings
        expand_frame = tk.LabelFrame(
            self,
            text="Expansion (pixels)",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        expand_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        grid = tk.Frame(expand_frame, bg=COLORS["bg_panel"])
        grid.pack(fill=tk.X, padx=5, pady=5)

        # Top
        tk.Label(
            grid,
            text="Top:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=0, column=0, sticky="w")
        self.top_var = tk.IntVar(
            value=self.config.get("outpaint_expand_top", 140)
        )
        tk.Entry(
            grid,
            textvariable=self.top_var,
            width=6,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=0, column=1, padx=5, pady=2)

        # Bottom
        tk.Label(
            grid,
            text="Bottom:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=0, column=2, sticky="w")
        self.bottom_var = tk.IntVar(
            value=self.config.get("outpaint_expand_bottom", 140)
        )
        tk.Entry(
            grid,
            textvariable=self.bottom_var,
            width=6,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=0, column=3, padx=5, pady=2)

        # Left
        tk.Label(
            grid,
            text="Left:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=1, column=0, sticky="w")
        self.left_var = tk.IntVar(
            value=self.config.get("outpaint_expand_left", 140)
        )
        tk.Entry(
            grid,
            textvariable=self.left_var,
            width=6,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=1, column=1, padx=5, pady=2)

        # Right
        tk.Label(
            grid,
            text="Right:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).grid(row=1, column=2, sticky="w")
        self.right_var = tk.IntVar(
            value=self.config.get("outpaint_expand_right", 140)
        )
        tk.Entry(
            grid,
            textvariable=self.right_var,
            width=6,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
        ).grid(row=1, column=3, padx=5, pady=2)

        # Preset buttons
        uniform_frame = tk.Frame(expand_frame, bg=COLORS["bg_panel"])
        uniform_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        for px, text in [(70, "70px"), (140, "140px"), (280, "280px")]:
            tk.Button(
                uniform_frame,
                text=text,
                font=(FONT_FAMILY, 8),
                bg=COLORS["bg_input"],
                fg=COLORS["text_light"],
                command=lambda p=px: self._set_uniform(p),
                cursor="hand2",
                relief=tk.FLAT,
                padx=6,
            ).pack(side=tk.LEFT, padx=2)

        # Prompt (optional)
        prompt_frame = tk.LabelFrame(
            self,
            text="Guidance Prompt (optional)",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        )
        prompt_frame.pack(fill=tk.X, padx=10, pady=5)

        self.prompt_text = tk.Text(
            prompt_frame,
            height=2,
            wrap=tk.WORD,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            insertbackground=COLORS["text_light"],
            padx=5,
            pady=5,
        )
        self.prompt_text.pack(fill=tk.X, padx=5, pady=5)
        self.prompt_text.insert(
            "1.0", self.config.get("outpaint_prompt", "")
        )

        # Output format
        fmt_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        fmt_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            fmt_frame,
            text="Output Format:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT)
        self.format_var = tk.StringVar(
            value=self.config.get("outpaint_format", "png")
        )
        ttk.Combobox(
            fmt_frame,
            textvariable=self.format_var,
            values=["png", "jpg"],
            state="readonly",
            width=6,
        ).pack(side=tk.LEFT, padx=5)

        # Expand button
        btn_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        self.expand_btn = tk.Button(
            btn_frame,
            text="Expand Image",
            font=(FONT_FAMILY, 11, "bold"),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_expand,
            cursor="hand2",
            relief=tk.FLAT,
            padx=20,
            pady=6,
        )
        self.expand_btn.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            btn_frame,
            text="",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

    def _set_uniform(self, px: int):
        """Set all expansion values uniformly."""
        for var in [
            self.top_var,
            self.bottom_var,
            self.left_var,
            self.right_var,
        ]:
            var.set(px)

    def _on_expand(self):
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

        output_folder = config.get("output_folder", "")
        if not output_folder or not os.path.isdir(output_folder):
            output_folder = os.path.dirname(image_path)

        self._set_busy(True)
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        expand_left = self.left_var.get()
        expand_right = self.right_var.get()
        expand_top = self.top_var.get()
        expand_bottom = self.bottom_var.get()
        output_format = self.format_var.get()

        def _run():
            try:
                from outpaint_generator import OutpaintGenerator

                gen = OutpaintGenerator(api_key)
                gen.set_progress_callback(
                    lambda msg, lvl: self.log(msg, lvl)
                )
                result = gen.outpaint(
                    image_path=image_path,
                    output_folder=output_folder,
                    expand_left=expand_left,
                    expand_right=expand_right,
                    expand_top=expand_top,
                    expand_bottom=expand_bottom,
                    prompt=prompt,
                    output_format=output_format,
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
            self.image_session.add_image(result, "outpaint")
            self.log(
                f"Outpaint complete: {os.path.basename(result)}", "success"
            )
        else:
            self.log("Outpaint failed", "error")

    def _on_error(self, error):
        self._set_busy(False)
        self.log(f"Error: {error}", "error")

    def _set_busy(self, busy):
        self._busy = busy
        self.expand_btn.config(
            state=tk.DISABLED if busy else tk.NORMAL,
            text="Expanding..." if busy else "Expand Image",
        )
        self.status_label.config(
            text="Processing..." if busy else "",
            fg=COLORS["progress"] if busy else COLORS["text_dim"],
        )

    def get_config_updates(self) -> dict:
        return {
            "outpaint_expand_left": self.left_var.get(),
            "outpaint_expand_right": self.right_var.get(),
            "outpaint_expand_top": self.top_var.get(),
            "outpaint_expand_bottom": self.bottom_var.get(),
            "outpaint_prompt": self.prompt_text.get("1.0", tk.END).strip(),
            "outpaint_format": self.format_var.get(),
        }
