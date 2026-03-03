"""
Model Manager Dialog - Add, test, hide/restore models from the GUI.

Manages two config keys:
  - custom_models: list of user-added model dicts (each has "custom": True)
  - hidden_models: list of endpoint strings for factory models the user hid
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
from typing import List, Dict, Optional, Callable

from .theme import COLORS, FONT_FAMILY
from model_metadata import MODEL_METADATA, get_model_display_name

logger = logging.getLogger(__name__)

# Default duration options for the add-model form
_DURATION_CHOICES = [5, 10]


class ModelManagerDialog(tk.Toplevel):
    """Modal dialog for managing the model list (factory + custom)."""

    def __init__(
        self,
        parent: tk.Widget,
        config: dict,
        api_key: str,
        on_save: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.title("Model Manager")
        self.configure(bg=COLORS["bg_main"])
        self.resizable(True, True)
        self.minsize(780, 480)
        self.geometry("820x540")

        self._config = config
        self._api_key = api_key
        self._on_save = on_save

        # Work on local copies — committed to config only on Save
        self._custom_models: List[Dict] = [
            dict(m) for m in config.get("custom_models", [])
        ]
        self._hidden_endpoints: List[str] = list(
            config.get("hidden_models", [])
        )

        # Combined model list (rebuilt on any change)
        self._all_models: List[Dict] = []
        self._health_cache: Dict[str, Optional[bool]] = {}  # endpoint -> True/False/None

        self._build_ui()
        self._rebuild_model_list()

        # Modal behavior
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.focus_set()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Main horizontal split: left (list) | right (add form)
        body = tk.Frame(self, bg=COLORS["bg_main"])
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 0))

        self._build_left_panel(body)
        self._build_right_panel(body)
        self._build_footer()

    def _build_left_panel(self, parent: tk.Frame):
        """Left panel: model listbox + action buttons."""
        left = tk.LabelFrame(
            parent, text="  Models  ", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["text_light"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        # Listbox with scrollbar
        list_frame = tk.Frame(left, bg=COLORS["bg_panel"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 4))

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self._listbox = tk.Listbox(
            list_frame, font=(FONT_FAMILY, 10),
            bg=COLORS["bg_main"], fg=COLORS["text_light"],
            selectbackground=COLORS["accent_blue"], selectforeground="#FFFFFF",
            activestyle="none", borderwidth=0, highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self._listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Action buttons row
        btn_row = tk.Frame(left, bg=COLORS["bg_panel"])
        btn_row.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._test_btn = tk.Button(
            btn_row, text="Test Selected", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_light"],
            activebackground=COLORS["bg_main"], activeforeground=COLORS["text_light"],
            relief=tk.FLAT, padx=8, pady=3, command=self._test_selected,
        )
        self._test_btn.pack(side=tk.LEFT, padx=(0, 4))

        self._remove_btn = tk.Button(
            btn_row, text="Remove", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["btn_red"], fg=COLORS["text_light"],
            activebackground="#963232", activeforeground=COLORS["text_light"],
            relief=tk.FLAT, padx=8, pady=3, command=self._remove_selected,
        )
        self._remove_btn.pack(side=tk.LEFT, padx=(0, 4))

        self._restore_btn = tk.Button(
            btn_row, text="Restore Hidden", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_light"],
            activebackground=COLORS["bg_main"], activeforeground=COLORS["text_light"],
            relief=tk.FLAT, padx=8, pady=3, command=self._restore_hidden,
        )
        self._restore_btn.pack(side=tk.LEFT)

    def _build_right_panel(self, parent: tk.Frame):
        """Right panel: add custom model form."""
        right = tk.LabelFrame(
            parent, text="  Add Custom Model  ", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["text_light"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        right.pack(side=tk.LEFT, fill=tk.BOTH, padx=(6, 0), ipadx=4)
        right.configure(width=300)

        inner = tk.Frame(right, bg=COLORS["bg_panel"])
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        lbl_opts = dict(font=(FONT_FAMILY, 9, "bold"), bg=COLORS["bg_panel"], fg=COLORS["text_dim"], anchor="w")
        entry_opts = dict(
            font=(FONT_FAMILY, 10), bg=COLORS["bg_main"], fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"], relief=tk.FLAT,
            highlightthickness=1, highlightbackground=COLORS["border"],
        )

        # Name
        tk.Label(inner, text="Name:", **lbl_opts).pack(fill=tk.X, pady=(0, 2))
        self._name_var = tk.StringVar()
        tk.Entry(inner, textvariable=self._name_var, **entry_opts).pack(fill=tk.X, pady=(0, 8))

        # Endpoint
        tk.Label(inner, text="Endpoint:", **lbl_opts).pack(fill=tk.X, pady=(0, 2))
        self._endpoint_var = tk.StringVar()
        tk.Entry(inner, textvariable=self._endpoint_var, **entry_opts).pack(fill=tk.X, pady=(0, 2))
        tk.Label(
            inner, text="e.g. fal-ai/kling-video/v3/pro/image-to-video",
            font=(FONT_FAMILY, 8), bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
        ).pack(anchor="w", pady=(0, 8))

        # Duration checkboxes
        tk.Label(inner, text="Durations:", **lbl_opts).pack(fill=tk.X, pady=(0, 2))
        dur_frame = tk.Frame(inner, bg=COLORS["bg_panel"])
        dur_frame.pack(fill=tk.X, pady=(0, 4))

        self._dur_5_var = tk.BooleanVar(value=True)
        self._dur_10_var = tk.BooleanVar(value=True)
        cb_opts = dict(
            font=(FONT_FAMILY, 9), bg=COLORS["bg_panel"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_panel"],
            activeforeground=COLORS["text_light"],
        )
        tk.Checkbutton(dur_frame, text="5s", variable=self._dur_5_var, **cb_opts).pack(side=tk.LEFT, padx=(0, 8))
        tk.Checkbutton(dur_frame, text="10s", variable=self._dur_10_var, **cb_opts).pack(side=tk.LEFT, padx=(0, 8))

        # Default duration
        tk.Label(inner, text="Default:", **lbl_opts).pack(fill=tk.X, pady=(0, 2))
        self._default_dur_var = tk.StringVar(value="5")
        def_dur_frame = tk.Frame(inner, bg=COLORS["bg_panel"])
        def_dur_frame.pack(fill=tk.X, pady=(0, 8))
        rb_opts = dict(
            font=(FONT_FAMILY, 9), bg=COLORS["bg_panel"], fg=COLORS["text_light"],
            selectcolor=COLORS["bg_main"], activebackground=COLORS["bg_panel"],
            activeforeground=COLORS["text_light"],
        )
        tk.Radiobutton(def_dur_frame, text="5s", variable=self._default_dur_var, value="5", **rb_opts).pack(side=tk.LEFT, padx=(0, 8))
        tk.Radiobutton(def_dur_frame, text="10s", variable=self._default_dur_var, value="10", **rb_opts).pack(side=tk.LEFT)

        # Notes
        tk.Label(inner, text="Notes (optional):", **lbl_opts).pack(fill=tk.X, pady=(0, 2))
        self._notes_text = tk.Text(
            inner, font=(FONT_FAMILY, 9), height=3,
            bg=COLORS["bg_main"], fg=COLORS["text_light"],
            insertbackground=COLORS["text_light"], relief=tk.FLAT,
            borderwidth=0, highlightthickness=1, highlightbackground=COLORS["border"],
            wrap=tk.WORD,
        )
        self._notes_text.pack(fill=tk.X, pady=(0, 8))

        # Test + Add buttons
        form_btns = tk.Frame(inner, bg=COLORS["bg_panel"])
        form_btns.pack(fill=tk.X, pady=(0, 4))

        self._test_new_btn = tk.Button(
            form_btns, text="Test", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_light"],
            activebackground=COLORS["bg_main"], activeforeground=COLORS["text_light"],
            relief=tk.FLAT, padx=10, pady=3, command=self._test_new_endpoint,
        )
        self._test_new_btn.pack(side=tk.LEFT, padx=(0, 4))

        self._add_btn = tk.Button(
            form_btns, text="Add", font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["btn_green"], fg=COLORS["text_light"],
            activebackground="#287028", activeforeground=COLORS["text_light"],
            relief=tk.FLAT, padx=10, pady=3, command=self._add_custom_model,
        )
        self._add_btn.pack(side=tk.LEFT)

        # Test result area (multi-line for capability info)
        self._test_result_text = tk.Text(
            inner, font=(FONT_FAMILY, 9), height=6,
            bg=COLORS["bg_panel"], fg=COLORS["text_dim"],
            relief=tk.FLAT, borderwidth=0, wrap=tk.WORD,
            state="disabled",
        )
        self._test_result_text.pack(fill=tk.BOTH, expand=True)
        self._test_result_text.tag_configure("success", foreground=COLORS["success"])
        self._test_result_text.tag_configure("error", foreground=COLORS["error"])
        self._test_result_text.tag_configure("warning", foreground=COLORS["warning"])
        self._test_result_text.tag_configure("info", foreground=COLORS["text_light"])
        self._test_result_text.tag_configure("dim", foreground=COLORS["text_dim"])

    def _build_footer(self):
        """Footer with Cancel / Save buttons."""
        footer = tk.Frame(self, bg=COLORS["bg_main"])
        footer.pack(fill=tk.X, padx=12, pady=10)

        tk.Button(
            footer, text="Save", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["btn_green"], fg=COLORS["text_light"],
            activebackground="#287028", activeforeground=COLORS["text_light"],
            relief=tk.FLAT, padx=16, pady=4, command=self._on_save_click,
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            footer, text="Cancel", font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["bg_input"], fg=COLORS["text_light"],
            activebackground=COLORS["bg_main"], activeforeground=COLORS["text_light"],
            relief=tk.FLAT, padx=16, pady=4, command=self._on_cancel,
        ).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Model list management
    # ------------------------------------------------------------------

    def _rebuild_model_list(self):
        """Rebuild the combined model list and refresh the listbox."""
        self._all_models = []

        # Factory models (from MODEL_METADATA / models.json)
        for m in MODEL_METADATA:
            entry = dict(m)
            ep = entry.get("endpoint", "")
            entry["_factory"] = True
            entry["_hidden"] = ep in self._hidden_endpoints
            self._all_models.append(entry)

        # Custom models
        for m in self._custom_models:
            entry = dict(m)
            entry["_factory"] = False
            entry["_hidden"] = False
            entry["custom"] = True
            self._all_models.append(entry)

        self._refresh_listbox()

    def _refresh_listbox(self):
        """Redraw the listbox from self._all_models."""
        self._listbox.delete(0, tk.END)

        for m in self._all_models:
            ep = m.get("endpoint", "")
            name = m.get("name", ep)
            is_hidden = m.get("_hidden", False)
            is_custom = not m.get("_factory", True)

            # Build display string
            prefix = "\u2605 " if is_custom else ""  # ★ for custom
            suffix = ""
            if is_hidden:
                suffix += "  [hidden]"

            health = self._health_cache.get(ep)
            if health is True:
                suffix += "  \u2714"  # ✔
            elif health is False:
                suffix += "  \u2718 UNAVAILABLE"  # ✘

            display = f"{prefix}{name}{suffix}"
            self._listbox.insert(tk.END, display)

            # Color coding
            idx = self._listbox.size() - 1
            if is_hidden:
                self._listbox.itemconfig(idx, fg=COLORS["text_dim"])
            elif health is False:
                self._listbox.itemconfig(idx, fg=COLORS["error"])
            elif is_custom:
                self._listbox.itemconfig(idx, fg=COLORS["accent_blue"])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _get_selected_index(self) -> Optional[int]:
        sel = self._listbox.curselection()
        if not sel:
            return None
        return sel[0]

    def _test_selected(self):
        """Test the health of the selected model endpoint."""
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("Test", "Select a model first.", parent=self)
            return

        model = self._all_models[idx]
        ep = model.get("endpoint", "")
        if not ep:
            return

        self._test_btn.config(state="disabled", text="Testing...")

        def _check():
            try:
                from model_schema_manager import check_endpoint_health
                alive = check_endpoint_health(self._api_key, ep)
            except Exception:
                alive = None
            self.after(0, self._on_test_result, ep, alive, True)

        threading.Thread(target=_check, daemon=True).start()

    def _on_test_result(self, endpoint: str, alive: Optional[bool], is_list_test: bool,
                        caps: dict = None, pricing: dict = None, meta: dict = None):
        """Handle test result on main thread."""
        self._health_cache[endpoint] = alive

        if is_list_test:
            self._test_btn.config(state="normal", text="Test Selected")
            self._refresh_listbox()
        else:
            # Result for the add-form test
            self._test_new_btn.config(state="normal", text="Test")
            self._set_test_result_text(alive, caps, pricing, meta)

            # Auto-populate name from API if user hasn't entered one
            if alive and meta and meta.get("display_name") and not self._name_var.get().strip():
                self._name_var.set(meta["display_name"])

    def _set_test_result_text(self, alive: Optional[bool], caps: dict = None,
                               pricing: dict = None, meta: dict = None):
        """Write multi-line test result into the result text widget."""
        self._test_result_text.config(state="normal")
        self._test_result_text.delete("1.0", tk.END)

        if alive is True:
            self._test_result_text.insert(tk.END, "\u2714 Endpoint is alive\n", "success")

            # Model name from API
            if meta and meta.get("display_name"):
                self._test_result_text.insert(tk.END, f"  Name: {meta['display_name']}\n", "info")

            # Pricing
            if pricing:
                unit = pricing.get("unit", "")
                price = pricing.get("unit_price", 0)
                if price:
                    if unit == "second":
                        price_str = f"${price:.3f}/second"
                    elif unit == "video":
                        price_str = f"${price:.2f}/video"
                    else:
                        price_str = f"${price:.3f}/{unit}" if unit else f"${price:.3f}"
                    self._test_result_text.insert(tk.END, f"  Pricing: {price_str}\n", "info")

            # Capabilities
            if caps:
                # Duration range
                durations = caps.get("duration_options", [])
                if durations:
                    dur_str = f"{min(durations)}-{max(durations)}s" if len(durations) > 1 else f"{durations[0]}s"
                else:
                    dur_str = "N/A"

                # Aspect ratios
                aspects = caps.get("aspect_ratios", [])
                ar_str = ", ".join(aspects) if aspects else "N/A"

                self._test_result_text.insert(
                    tk.END, f"  Durations: {dur_str} | Aspect: {ar_str}\n", "dim"
                )

                # Feature flags
                flags = []
                flag_map = [
                    ("supports_audio", "Audio"),
                    ("supports_camera_fixed", "Camera Lock"),
                    ("supports_seed", "Seed"),
                    ("supports_resolution", "Resolution"),
                    ("supports_negative_prompt", "Neg Prompt"),
                ]
                for key, label in flag_map:
                    icon = "\u2713" if caps.get(key) else "\u2717"
                    flags.append(f"{icon} {label}")

                self._test_result_text.insert(tk.END, f"  {' | '.join(flags)}\n", "dim")

        elif alive is False:
            self._test_result_text.insert(tk.END, "\u2718 Endpoint unavailable (404)", "error")
        else:
            self._test_result_text.insert(tk.END, "? Could not determine status", "warning")

        self._test_result_text.config(state="disabled")

    def _remove_selected(self):
        """Remove/hide the selected model."""
        idx = self._get_selected_index()
        if idx is None:
            messagebox.showinfo("Remove", "Select a model first.", parent=self)
            return

        model = self._all_models[idx]
        ep = model.get("endpoint", "")
        is_factory = model.get("_factory", True)

        if is_factory:
            # Factory models get hidden, not deleted
            if model.get("_hidden"):
                messagebox.showinfo("Remove", "This model is already hidden.", parent=self)
                return
            if ep and ep not in self._hidden_endpoints:
                self._hidden_endpoints.append(ep)
        else:
            # Custom models get actually removed
            self._custom_models = [
                m for m in self._custom_models if m.get("endpoint") != ep
            ]

        self._rebuild_model_list()

    def _restore_hidden(self):
        """Restore all hidden factory models."""
        if not self._hidden_endpoints:
            messagebox.showinfo("Restore", "No hidden models to restore.", parent=self)
            return

        count = len(self._hidden_endpoints)
        self._hidden_endpoints.clear()
        self._rebuild_model_list()
        messagebox.showinfo("Restored", f"Restored {count} hidden model(s).", parent=self)

    def _test_new_endpoint(self):
        """Test the endpoint entered in the add form + fetch capabilities."""
        ep = self._endpoint_var.get().strip()
        if not ep:
            self._test_result_text.config(state="normal")
            self._test_result_text.delete("1.0", tk.END)
            self._test_result_text.insert(tk.END, "Enter an endpoint first", "warning")
            self._test_result_text.config(state="disabled")
            return

        self._test_new_btn.config(state="disabled", text="Testing...")
        self._test_result_text.config(state="normal")
        self._test_result_text.delete("1.0", tk.END)
        self._test_result_text.insert(tk.END, "Checking endpoint...", "dim")
        self._test_result_text.config(state="disabled")

        def _check():
            caps = None
            pricing_info = None
            meta = None
            try:
                from model_schema_manager import check_endpoint_health, ModelSchemaManager
                alive = check_endpoint_health(self._api_key, ep)

                # If alive, also fetch schema capabilities + pricing + metadata
                if alive and self._api_key:
                    try:
                        schema_mgr = ModelSchemaManager(self._api_key)
                        caps = schema_mgr.extract_capabilities(ep)
                        pricing = schema_mgr.get_model_pricing([ep])
                        pricing_info = pricing.get(ep)
                        meta = schema_mgr.get_model_metadata(ep)
                    except Exception as e:
                        logger.debug(f"Capability fetch failed for {ep}: {e}")
            except Exception:
                alive = None
            self.after(0, self._on_test_result, ep, alive, False, caps, pricing_info, meta)

        threading.Thread(target=_check, daemon=True).start()

    def _add_custom_model(self):
        """Add a custom model from the form fields."""
        name = self._name_var.get().strip()
        endpoint = self._endpoint_var.get().strip()

        if not name:
            messagebox.showwarning("Missing Name", "Please enter a model name.", parent=self)
            return
        if not endpoint:
            messagebox.showwarning("Missing Endpoint", "Please enter a fal.ai endpoint.", parent=self)
            return

        # Duplicate check against all models
        all_endpoints = set()
        for m in MODEL_METADATA:
            all_endpoints.add(m.get("endpoint", ""))
        for m in self._custom_models:
            all_endpoints.add(m.get("endpoint", ""))

        if endpoint in all_endpoints:
            messagebox.showwarning(
                "Duplicate Endpoint",
                f"Endpoint already exists in the model list:\n{endpoint}",
                parent=self,
            )
            return

        # Build duration options
        durations = []
        if self._dur_5_var.get():
            durations.append(5)
        if self._dur_10_var.get():
            durations.append(10)
        if not durations:
            durations = [5]

        default_dur = int(self._default_dur_var.get())
        if default_dur not in durations:
            default_dur = durations[0]

        notes = self._notes_text.get("1.0", tk.END).strip()

        new_model = {
            "name": name,
            "endpoint": endpoint,
            "duration_options": durations,
            "duration_default": default_dur,
            "notes": notes,
            "custom": True,
        }

        self._custom_models.append(new_model)
        self._rebuild_model_list()

        # Clear form
        self._name_var.set("")
        self._endpoint_var.set("")
        self._dur_5_var.set(True)
        self._dur_10_var.set(True)
        self._default_dur_var.set("5")
        self._notes_text.delete("1.0", tk.END)
        self._test_result_text.config(state="normal")
        self._test_result_text.delete("1.0", tk.END)
        self._test_result_text.insert(tk.END, f"Added: {name}", "success")
        self._test_result_text.config(state="disabled")

    # ------------------------------------------------------------------
    # Save / Cancel
    # ------------------------------------------------------------------

    def _on_save_click(self):
        """Commit changes to config and close."""
        self._config["custom_models"] = self._custom_models
        self._config["hidden_models"] = self._hidden_endpoints

        # If the currently active model was hidden or removed, pick the first visible
        current_ep = self._config.get("current_model", "")
        visible_models = [
            m for m in self._all_models
            if not m.get("_hidden", False)
        ]
        current_still_visible = any(
            m.get("endpoint") == current_ep for m in visible_models
        )
        if not current_still_visible and visible_models:
            fallback = visible_models[0]
            self._config["current_model"] = fallback.get("endpoint", "")
            self._config["model_display_name"] = fallback.get("name", "")
            logger.info(
                f"Active model was removed/hidden; auto-selected: {fallback.get('name')}"
            )

        if self._on_save:
            self._on_save()

        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        """Discard changes and close."""
        self.grab_release()
        self.destroy()
