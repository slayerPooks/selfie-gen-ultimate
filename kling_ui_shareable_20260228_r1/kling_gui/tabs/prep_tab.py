"""Prep Tab — Vision analysis of portrait images."""

import tkinter as tk
from tkinter import ttk
import threading
from typing import Callable

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession


class PrepTab(tk.Frame):
    """Tab 1: Analyze portrait images using vision AI."""

    OPENROUTER_MODELS = [
        ("Seed 1.6 Flash", "bytedance-seed/seed-1.6-flash"),
        ("GPT-4o Mini", "openai/gpt-4o-mini"),
        ("Claude 3.5 Haiku", "anthropic/claude-3.5-haiku"),
        ("Gemini 2.0 Flash", "google/gemini-2.0-flash-001"),
    ]

    def __init__(
        self,
        parent,
        image_session: ImageSession,
        config: dict,
        config_getter: Callable[[], dict],
        log_callback: Callable[[str, str], None],
        prompt_writer: Callable[[str], None],
        **kwargs,
    ):
        """
        Args:
            parent: Parent widget
            image_session: Shared image session state
            config: Initial config dict
            config_getter: Function returning current config
            log_callback: log(message, level)
            prompt_writer: Function to write text into the active prompt slot
        """
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.image_session = image_session
        self.config = config
        self.get_config = config_getter
        self.log = log_callback
        self.prompt_writer = prompt_writer
        self._busy = False
        self._last_result = ""

        self._build_ui()

    def _build_ui(self):
        # API Key section
        key_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        key_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        tk.Label(
            key_frame,
            text="OpenRouter API Key:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT)

        self.api_key_var = tk.StringVar(
            value=self.config.get("openrouter_api_key", "")
        )
        self.key_entry = tk.Entry(
            key_frame,
            textvariable=self.api_key_var,
            show="*",
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            width=30,
        )
        self.key_entry.pack(
            side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True
        )

        # Model selection
        model_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        model_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            model_frame,
            text="Vision Model:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT)

        self.model_var = tk.StringVar()
        model_names = [m[0] for m in self.OPENROUTER_MODELS]
        self.model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=model_names,
            state="readonly",
            width=25,
        )
        saved_model = self.config.get(
            "openrouter_model", "bytedance-seed/seed-1.6-flash"
        )
        for i, (_name, endpoint) in enumerate(self.OPENROUTER_MODELS):
            if endpoint == saved_model:
                self.model_combo.current(i)
                break
        else:
            self.model_combo.current(0)
        self.model_combo.pack(side=tk.LEFT, padx=(5, 0))

        # Analyze button
        btn_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        self.analyze_btn = tk.Button(
            btn_frame,
            text="Analyze Image",
            font=(FONT_FAMILY, 11, "bold"),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_analyze,
            cursor="hand2",
            relief=tk.FLAT,
            padx=20,
            pady=6,
        )
        self.analyze_btn.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            btn_frame,
            text="",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Result display
        tk.Label(
            self,
            text="Analysis Result:",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(fill=tk.X, padx=10, pady=(5, 2))

        result_frame = tk.Frame(self, bg=COLORS["bg_main"])
        result_frame.pack(
            fill=tk.BOTH, expand=True, padx=10, pady=(0, 5)
        )

        self.result_text = tk.Text(
            result_frame,
            wrap=tk.WORD,
            height=6,
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            insertbackground=COLORS["text_light"],
            padx=5,
            pady=5,
            borderwidth=0,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(result_frame, command=self.result_text.yview)
        self.result_text.config(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Write to prompt button
        write_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        write_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.write_btn = tk.Button(
            write_frame,
            text="Write to Active Prompt Slot",
            font=(FONT_FAMILY, 9),
            bg=COLORS["btn_green"],
            fg="white",
            command=self._on_write_prompt,
            cursor="hand2",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            state=tk.DISABLED,
        )
        self.write_btn.pack(side=tk.LEFT)

    def _get_selected_model_endpoint(self) -> str:
        idx = self.model_combo.current()
        if 0 <= idx < len(self.OPENROUTER_MODELS):
            return self.OPENROUTER_MODELS[idx][1]
        return self.OPENROUTER_MODELS[0][1]

    def _on_analyze(self):
        if self._busy:
            return

        api_key = self.api_key_var.get().strip()
        if not api_key:
            self.log("OpenRouter API key required", "error")
            return

        image_path = self.image_session.active_image_path
        if not image_path:
            self.log("No image selected in carousel", "warning")
            return

        self._set_busy(True)
        self.write_btn.config(state=tk.DISABLED)
        model = self._get_selected_model_endpoint()

        def _run():
            try:
                from vision_analyzer import VisionAnalyzer

                analyzer = VisionAnalyzer(api_key, model)
                analyzer.set_progress_callback(
                    lambda msg, lvl: self.winfo_toplevel().after(
                        0, lambda m=msg, l=lvl: self.log(m, l)
                    )
                )
                result = analyzer.analyze_image(image_path)
                self.winfo_toplevel().after(
                    0, lambda: self._on_analyze_complete(result)
                )
            except Exception as e:
                err = str(e)
                self.winfo_toplevel().after(
                    0, lambda: self._on_analyze_error(err)
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_analyze_complete(self, result):
        self._set_busy(False)
        if result and result.get("prompt"):
            self._last_result = result["prompt"]
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert("1.0", self._last_result)
            self.write_btn.config(state=tk.NORMAL)
            self.log("Analysis complete — review result below", "success")
        else:
            self._last_result = ""
            self.result_text.delete("1.0", tk.END)
            self.write_btn.config(state=tk.DISABLED)
            self.log("Analysis returned no result", "warning")

    def _on_analyze_error(self, error: str):
        self._set_busy(False)
        self.write_btn.config(state=tk.DISABLED)
        self.log(f"Analysis error: {error}", "error")

    def _on_write_prompt(self):
        text = self.result_text.get("1.0", tk.END).strip()
        if text:
            self.prompt_writer(text)
            self.log("Prompt written to active slot", "success")

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.analyze_btn.config(
            state=tk.DISABLED if busy else tk.NORMAL,
            text="Analyzing..." if busy else "Analyze Image",
        )
        self.status_label.config(
            text="Processing..." if busy else "",
            fg=COLORS["progress"] if busy else COLORS["text_dim"],
        )

    def get_config_updates(self) -> dict:
        """Return config values to save."""
        return {
            "openrouter_api_key": self.api_key_var.get().strip(),
            "openrouter_model": self._get_selected_model_endpoint(),
        }
