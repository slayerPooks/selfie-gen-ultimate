"""Image Carousel Widget — unified carousel showing all images with hover preview."""

import tkinter as tk
from tkinter import filedialog
from typing import Callable, Optional
import os
import logging

from .theme import COLORS, FONT_FAMILY
from .image_state import ImageSession

logger = logging.getLogger(__name__)

# Type label → display tag + color
_TYPE_LABELS = {
    "input": ("[ORIGINAL]", COLORS["accent_blue"]),
    "selfie": ("[GENERATED]", COLORS["success"]),
    "outpaint": ("[EXPANDED]", COLORS["warning"]),
}


class ImageCarousel(tk.Frame):
    """Unified carousel showing all images (input + selfie + outpaint) in one stream.

    Same constructor signature as before so main_window.py needs minimal changes.
    """

    def __init__(
        self,
        parent,
        image_session: ImageSession,
        log_callback: Callable[[str, str], None],
        **kwargs,
    ):
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.image_session = image_session
        self.log = log_callback

        # PhotoImage ref to prevent GC
        self._photo: Optional[tk.PhotoImage] = None

        # Hover preview state
        self._hover_popup: Optional[tk.Toplevel] = None
        self._hover_photo = None
        self._hover_job: Optional[str] = None

        # Compare callback (set by main_window)
        self._on_compare_callback: Optional[Callable[[], None]] = None

        # Re-entrancy guard
        self._updating: bool = False

        self._build_panel()

        # Listen for session changes
        self.image_session.set_on_change(self._on_session_change)

    # ── Public API ──────────────────────────────────────────────────

    def set_on_compare(self, callback: Callable[[], None]):
        """Register the callback invoked when the Compare button is clicked."""
        self._on_compare_callback = callback

    # ── Panel layout ────────────────────────────────────────────────

    def _build_panel(self):
        self.panel_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        self.panel_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Header row
        header = tk.Frame(self.panel_frame, bg=COLORS["bg_panel"])
        header.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(5, 2))

        tk.Label(
            header,
            text="IMAGE CAROUSEL",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT)

        # Add button (rightmost)
        add_btn = tk.Button(
            header,
            text="+ Add",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._on_add_image,
            cursor="hand2",
            relief=tk.FLAT,
            padx=6,
        )
        add_btn.pack(side=tk.RIGHT)

        # Remove button
        self.remove_btn = tk.Button(
            header,
            text="- Remove",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"],
            fg=COLORS["error"],
            command=self._on_remove_image,
            cursor="hand2",
            relief=tk.FLAT,
            padx=6,
            state=tk.DISABLED,
        )
        self.remove_btn.pack(side=tk.RIGHT, padx=(0, 4))

        # Compare button
        self.compare_btn = tk.Button(
            header,
            text="Compare",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._on_compare,
            cursor="hand2",
            relief=tk.FLAT,
            padx=6,
            state=tk.DISABLED,
        )
        self.compare_btn.pack(side=tk.RIGHT, padx=(0, 4))

        # Nav buttons + counter
        self.next_btn = tk.Button(
            header,
            text=">",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=lambda: self.image_session.navigate(1),
            width=2,
            cursor="hand2",
            relief=tk.FLAT,
        )
        self.next_btn.pack(side=tk.RIGHT, padx=(2, 4))

        self.counter_label = tk.Label(
            header,
            text="",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.counter_label.pack(side=tk.RIGHT, padx=2)

        self.prev_btn = tk.Button(
            header,
            text="<",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=lambda: self.image_session.navigate(-1),
            width=2,
            cursor="hand2",
            relief=tk.FLAT,
        )
        self.prev_btn.pack(side=tk.RIGHT)

        # Info label at bottom
        self.info_label = tk.Label(
            self.panel_frame,
            text="",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.info_label.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 2))

        # Canvas for image display
        self.canvas = tk.Canvas(
            self.panel_frame, bg=COLORS["bg_main"], highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)
        self.canvas.bind("<Configure>", lambda _e: self._update_display())
        self.canvas.bind("<Enter>", self._on_canvas_enter)
        self.canvas.bind("<Leave>", self._on_hover_leave)

    # ── Session change handler ──────────────────────────────────────

    def _on_session_change(self):
        self._update_display()
        self.after(50, self._update_display)

    # ── Main update ─────────────────────────────────────────────────

    def _update_display(self):
        if self._updating:
            return
        self._updating = True
        try:
            self._update_panel()
        finally:
            self._updating = False

    def _update_panel(self):
        self.canvas.delete("all")
        session = self.image_session
        entry = session.active_entry
        n = session.count

        # Button states
        self.remove_btn.config(state=tk.NORMAL if n > 0 else tk.DISABLED)
        self.compare_btn.config(state=tk.NORMAL if n >= 2 else tk.DISABLED)

        nav_state = tk.NORMAL if n > 1 else tk.DISABLED
        self.prev_btn.config(state=nav_state)
        self.next_btn.config(state=nav_state)

        if n == 0:
            self.counter_label.config(text="")
            self.info_label.config(text="Add images to start", fg=COLORS["text_dim"])
            cw = max(1, self.canvas.winfo_width())
            ch = max(1, self.canvas.winfo_height())
            self.canvas.create_text(
                cw // 2,
                ch // 2,
                text="Add images to start",
                fill=COLORS["text_dim"],
                font=(FONT_FAMILY, 10),
            )
            return

        # Counter
        self.counter_label.config(text=f"{session.current_index + 1}/{n}")

        # Show the active image
        if entry and entry.exists:
            self._show_image_on_canvas(self.canvas, entry.path, "_photo")

            # Type-colored info label
            tag, color = _TYPE_LABELS.get(
                entry.source_type, (f"[{entry.source_type.upper()}]", COLORS["text_dim"])
            )
            # Build detail: use custom label part if present, else filename
            detail = entry.filename
            default_label = f"{entry.source_type}: {entry.filename}"
            if entry.label and entry.label != default_label:
                detail = entry.label.replace(f"{entry.source_type}: ", "", 1)
            self.info_label.config(text=f"{tag} {detail}", fg=color)
        elif entry:
            self.info_label.config(text="File not found", fg=COLORS["error"])

    # ── Image rendering helper ──────────────────────────────────────

    def _show_image_on_canvas(self, canvas: tk.Canvas, path: str, attr_name: str):
        """Load and display an image on a canvas, aspect-fitted."""
        try:
            from PIL import Image, ImageTk

            img = Image.open(path)
            img.load()
            cw = max(1, canvas.winfo_width() - 4)
            ch = max(1, canvas.winfo_height() - 4)

            ratio = min(cw / img.width, ch / img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            setattr(self, attr_name, photo)
            canvas.create_image(
                cw // 2 + 2, ch // 2 + 2, image=photo, anchor=tk.CENTER
            )
        except ImportError:
            cw = max(1, canvas.winfo_width())
            ch = max(1, canvas.winfo_height())
            canvas.create_text(
                cw // 2, ch // 2,
                text="PIL not available",
                fill=COLORS["warning"],
                font=(FONT_FAMILY, 9),
            )
        except Exception as e:
            cw = max(1, canvas.winfo_width())
            ch = max(1, canvas.winfo_height())
            canvas.create_text(
                cw // 2, ch // 2,
                text=f"Cannot load: {e}",
                fill=COLORS["error"],
                font=(FONT_FAMILY, 9),
            )

    # ── Actions ─────────────────────────────────────────────────────

    def _on_add_image(self):
        """Open file dialog to add image(s) to session as input."""
        filetypes = [
            (
                "Image files",
                "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff *.tif",
            ),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(
            title="Select Images", filetypes=filetypes
        )
        for p in paths:
            self.image_session.add_image(p, "input")
            self.log(f"Added to carousel: {os.path.basename(p)}", "info")

    def _on_remove_image(self):
        """Remove the currently active image from the carousel."""
        entry = self.image_session.active_entry
        if entry is None:
            return
        name = entry.filename
        self.image_session.remove_current()
        self.log(f"Removed from carousel: {name}", "info")

    def _on_compare(self):
        if self._on_compare_callback:
            self._on_compare_callback()

    # ── Hover preview ───────────────────────────────────────────────

    def _on_canvas_enter(self, event):
        entry = self.image_session.active_entry
        if entry and entry.exists:
            self._schedule_hover(entry.path, event)

    def _schedule_hover(self, path: str, event):
        self._cancel_hover()
        self._hover_job = self.after(
            500, lambda: self._show_hover_preview(path, event)
        )

    def _cancel_hover(self):
        if self._hover_job:
            self.after_cancel(self._hover_job)
            self._hover_job = None

    def _on_hover_leave(self, _event=None):
        self._cancel_hover()
        self._destroy_hover()

    def _destroy_hover(self):
        if self._hover_popup:
            try:
                self._hover_popup.destroy()
            except tk.TclError:
                pass
            self._hover_popup = None
            self._hover_photo = None

    def _show_hover_preview(self, path: str, event):
        """Show a borderless popup with a large preview of the image."""
        self._destroy_hover()
        try:
            from PIL import Image, ImageTk

            img = Image.open(path)
            img.load()

            max_dim = 600
            ratio = min(max_dim / img.width, max_dim / img.height, 1.0)
            if ratio < 1.0:
                new_w = max(1, int(img.width * ratio))
                new_h = max(1, int(img.height * ratio))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self._hover_photo = photo

            popup = tk.Toplevel(self)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)
            popup.config(bg=COLORS["bg_main"])

            label = tk.Label(popup, image=photo, bg=COLORS["bg_main"], bd=1, relief=tk.SOLID)
            label.pack()

            x = event.x_root + 20
            y = event.y_root + 10
            popup.update_idletasks()
            pw = popup.winfo_reqwidth()
            ph = popup.winfo_reqheight()
            sw = popup.winfo_screenwidth()
            sh = popup.winfo_screenheight()

            if x + pw > sw:
                x = event.x_root - pw - 20
            if y + ph > sh:
                y = event.y_root - ph - 10
            x = max(0, x)
            y = max(0, y)

            popup.geometry(f"+{x}+{y}")

            popup.bind("<Leave>", self._on_hover_leave)
            popup.bind("<Button-1>", self._on_hover_leave)

            self._hover_popup = popup
        except Exception as e:
            logger.debug("Hover preview error: %s", e)
