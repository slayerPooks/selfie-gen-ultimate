"""Compare Panel — side-by-side image comparison with independent navigation."""

import tkinter as tk
from typing import Callable, Optional
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


class ComparePanel(tk.Frame):
    """Comparison panel with independent navigation through all session images."""

    def __init__(
        self,
        parent,
        image_session: ImageSession,
        log_callback: Callable[[str, str], None],
        on_close: Callable[[], None],
        **kwargs,
    ):
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.image_session = image_session
        self.log = log_callback
        self._on_close = on_close

        # Independent navigation index
        self._compare_index: int = -1

        # PhotoImage ref to prevent GC
        self._photo: Optional[tk.PhotoImage] = None

        # Re-entrancy guard
        self._updating: bool = False

        self._build_panel()

        # Pick initial compare index (next image after current)
        self._init_compare_index()

        # Listen for session changes
        self.image_session.add_on_change(self._on_session_change)

        self._update_display()

    def destroy(self):
        self.image_session.remove_on_change(self._on_session_change)
        super().destroy()

    def _on_session_change(self):
        """Called when the image session changes — update our display."""
        # Clamp compare index if images were removed
        if self.image_session.count == 0:
            self._compare_index = -1
        elif self._compare_index >= self.image_session.count:
            self._compare_index = self.image_session.count - 1
        self._update_display()

    def _init_compare_index(self):
        n = self.image_session.count
        if n < 2:
            self._compare_index = -1
            return
        current = self.image_session.current_index
        self._compare_index = (current + 1) % n

    # ── Panel layout ────────────────────────────────────────────────

    def _build_panel(self):
        # Header row
        header = tk.Frame(self, bg=COLORS["bg_panel"])
        header.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(5, 2))

        tk.Label(
            header,
            text="COMPARE",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT)

        # Close button
        close_btn = tk.Button(
            header,
            text="X Close",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_input"],
            fg=COLORS["error"],
            command=self._on_close,
            cursor="hand2",
            relief=tk.FLAT,
            padx=6,
        )
        close_btn.pack(side=tk.RIGHT)

        # Nav buttons + counter
        self.next_btn = tk.Button(
            header,
            text=">",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=lambda: self._navigate(1),
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
            command=lambda: self._navigate(-1),
            width=2,
            cursor="hand2",
            relief=tk.FLAT,
        )
        self.prev_btn.pack(side=tk.RIGHT)

        # Info label at bottom
        self.info_label = tk.Label(
            self,
            text="",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.info_label.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 2))

        # Canvas for image
        self.canvas = tk.Canvas(self, bg=COLORS["bg_main"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)
        self.canvas.bind("<Configure>", lambda _e: self._update_display())

    # ── Navigation ──────────────────────────────────────────────────

    def _navigate(self, delta: int):
        n = self.image_session.count
        if n < 2:
            return
        self._compare_index = (self._compare_index + delta) % n
        self._update_display()

    # ── Display ─────────────────────────────────────────────────────

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
        n = self.image_session.count

        nav_state = tk.NORMAL if n > 1 else tk.DISABLED
        self.prev_btn.config(state=nav_state)
        self.next_btn.config(state=nav_state)

        if n == 0 or self._compare_index < 0:
            self.counter_label.config(text="")
            self.info_label.config(text="No images to compare", fg=COLORS["text_dim"])
            return

        # Clamp index
        if self._compare_index >= n:
            self._compare_index = n - 1

        self.counter_label.config(text=f"{self._compare_index + 1}/{n}")

        images = self.image_session.images
        entry = images[self._compare_index]

        if entry.exists:
            self._show_image_on_canvas(entry.path)
            tag, color = _TYPE_LABELS.get(
                entry.source_type, (f"[{entry.source_type.upper()}]", COLORS["text_dim"])
            )
            detail = entry.filename
            default_label = f"{entry.source_type}: {entry.filename}"
            if entry.label and entry.label != default_label:
                detail = entry.label.replace(f"{entry.source_type}: ", "", 1)
            self.info_label.config(text=f"{tag} {detail}", fg=color)
        else:
            self.info_label.config(text="File not found", fg=COLORS["error"])

    def _show_image_on_canvas(self, path: str):
        try:
            from PIL import Image, ImageTk

            img = Image.open(path)
            img.load()
            cw = max(1, self.canvas.winfo_width() - 4)
            ch = max(1, self.canvas.winfo_height() - 4)

            ratio = min(cw / img.width, ch / img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self._photo = photo
            self.canvas.create_image(
                cw // 2 + 2, ch // 2 + 2, image=photo, anchor=tk.CENTER
            )
        except ImportError:
            cw = max(1, self.canvas.winfo_width())
            ch = max(1, self.canvas.winfo_height())
            self.canvas.create_text(
                cw // 2, ch // 2,
                text="PIL not available",
                fill=COLORS["warning"],
                font=(FONT_FAMILY, 9),
            )
        except Exception as e:
            cw = max(1, self.canvas.winfo_width())
            ch = max(1, self.canvas.winfo_height())
            self.canvas.create_text(
                cw // 2, ch // 2,
                text=f"Cannot load: {e}",
                fill=COLORS["error"],
                font=(FONT_FAMILY, 9),
            )
