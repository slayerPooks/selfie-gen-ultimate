"""Prep Tab — Vision analysis of portrait images."""

import tkinter as tk
from tkinter import ttk
import threading
from typing import Callable, Optional

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession


class PrepTab(tk.Frame):
    """Tab 1: Analyze portrait images using vision AI."""

    BUILTIN_MODELS = [
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
        config_saver: Optional[Callable[[], None]] = None,
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
            config_saver: Function to persist config to disk immediately
        """
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.image_session = image_session
        self.config = config
        self.get_config = config_getter
        self.log = log_callback
        self.prompt_writer = prompt_writer
        self._config_saver = config_saver
        self._busy = False
        self._last_result = ""

        # Build combined model list: built-in + custom from config
        self._custom_models = list(config.get("openrouter_custom_models", []))
        self._all_models = list(self.BUILTIN_MODELS)
        for endpoint in self._custom_models:
            self._all_models.append((endpoint, endpoint))

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

        self.save_key_btn = tk.Button(
            key_frame,
            text="Save",
            font=(FONT_FAMILY, 8),
            bg=COLORS["btn_green"],
            fg="white",
            command=self._on_save_key,
            cursor="hand2",
            relief=tk.FLAT,
            padx=8,
            pady=1,
        )
        self.save_key_btn.pack(side=tk.LEFT, padx=(5, 0))

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
        model_names = [m[0] for m in self._all_models]
        self.model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=model_names,
            state="readonly",
            width=30,
        )
        saved_model = self.config.get(
            "openrouter_model", "bytedance-seed/seed-1.6-flash"
        )
        for i, (_name, endpoint) in enumerate(self._all_models):
            if endpoint == saved_model:
                self.model_combo.current(i)
                break
        else:
            self.model_combo.current(0)
        self.model_combo.pack(side=tk.LEFT, padx=(5, 0))

        self.remove_model_btn = tk.Button(
            model_frame,
            text="Remove",
            font=(FONT_FAMILY, 8),
            bg=COLORS["btn_red"],
            fg="white",
            command=self._on_remove_model,
            cursor="hand2",
            relief=tk.FLAT,
            padx=6,
            pady=1,
        )
        self.remove_model_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Custom model entry
        custom_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        custom_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        tk.Label(
            custom_frame,
            text="Add Custom:",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT)

        self.custom_model_var = tk.StringVar()
        self.custom_model_entry = tk.Entry(
            custom_frame,
            textvariable=self.custom_model_var,
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"],
            font=(FONT_FAMILY, 9),
            width=28,
        )
        self.custom_model_entry.pack(
            side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True
        )
        self.custom_model_entry.insert(0, "org/model-name")
        self.custom_model_entry.bind(
            "<FocusIn>", self._on_custom_entry_focus
        )

        self.add_model_btn = tk.Button(
            custom_frame,
            text="Add",
            font=(FONT_FAMILY, 8),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_add_model,
            cursor="hand2",
            relief=tk.FLAT,
            padx=8,
            pady=1,
        )
        self.add_model_btn.pack(side=tk.LEFT, padx=(5, 0))

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
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["btn_green"],
            fg="white",
            disabledforeground="#8FBC8F",
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
        if 0 <= idx < len(self._all_models):
            return self._all_models[idx][1]
        return self._all_models[0][1]

    def _save_config_now(self):
        """Update shared config dict and persist to disk."""
        self.config.update(self.get_config_updates())
        if self._config_saver:
            self._config_saver()

    def _on_save_key(self):
        key = self.api_key_var.get().strip()
        if not key:
            self.log("No API key to save", "warning")
            return
        self._save_config_now()
        self.log("API key saved", "success")

    def _refresh_model_combo(self):
        """Rebuild combobox values from _all_models."""
        names = [m[0] for m in self._all_models]
        self.model_combo["values"] = names

    def _on_add_model(self):
        endpoint = self.custom_model_var.get().strip()
        if not endpoint or endpoint == "org/model-name":
            self.log("Enter a model endpoint (e.g. meta-llama/llama-3-70b)", "warning")
            return
        if "/" not in endpoint or not endpoint.isascii() or " " in endpoint:
            self.log("Model endpoint should be org/model format (ASCII, no spaces)", "warning")
            return
        # Check for duplicates
        for _name, ep in self._all_models:
            if ep == endpoint:
                self.log(f"Model already in list: {endpoint}", "warning")
                return
        self._custom_models.append(endpoint)
        self._all_models.append((endpoint, endpoint))
        self._refresh_model_combo()
        # Select the newly added model
        self.model_combo.current(len(self._all_models) - 1)
        self.custom_model_var.set("")
        self._save_config_now()
        self.log(f"Added custom model: {endpoint}", "success")

    def _on_remove_model(self):
        idx = self.model_combo.current()
        if idx < 0:
            return
        _name, endpoint = self._all_models[idx]
        # Only allow removing custom models
        if endpoint not in self._custom_models:
            self.log("Cannot remove built-in models", "warning")
            return
        self._custom_models.remove(endpoint)
        self._all_models.pop(idx)
        self._refresh_model_combo()
        self.model_combo.current(0)
        self._save_config_now()
        self.log(f"Removed custom model: {endpoint}", "info")

    def _on_custom_entry_focus(self, _event):
        if self.custom_model_var.get() == "org/model-name":
            self.custom_model_var.set("")

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
            "openrouter_custom_models": list(self._custom_models),
        }
