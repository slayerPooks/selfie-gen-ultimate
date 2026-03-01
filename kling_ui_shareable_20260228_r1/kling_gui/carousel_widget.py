"""Image Carousel Widget — displays images with navigation."""

import tkinter as tk
from tkinter import filedialog
from typing import Callable
import os

from .theme import COLORS, FONT_FAMILY
from .image_state import ImageSession


class ImageCarousel(tk.Frame):
    """Image carousel for the bottom-left panel.

    Shows current image thumbnail with < > nav buttons, counter text,
    "Add Image" button, and source type info label.
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
        self._photo_ref = None  # prevent GC of PhotoImage

        # Header with title + Add button
        header = tk.Frame(self, bg=COLORS["bg_panel"])
        header.pack(fill=tk.X, padx=8, pady=(5, 2))

        tk.Label(
            header,
            text="IMAGE CAROUSEL",
            font=(FONT_FAMILY, 10, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT)

        add_btn = tk.Button(
            header,
            text="+ Add",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._on_add_image,
            cursor="hand2",
            relief=tk.FLAT,
            padx=8,
        )
        add_btn.pack(side=tk.RIGHT)

        # Image display area
        self.canvas = tk.Canvas(
            self, bg=COLORS["bg_main"], highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Navigation bar
        nav = tk.Frame(self, bg=COLORS["bg_panel"])
        nav.pack(fill=tk.X, padx=8, pady=(2, 5))

        self.prev_btn = tk.Button(
            nav,
            text="<",
            font=(FONT_FAMILY, 12, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=lambda: self._navigate(-1),
            width=3,
            cursor="hand2",
            relief=tk.FLAT,
        )
        self.prev_btn.pack(side=tk.LEFT)

        self.counter_label = tk.Label(
            nav,
            text="No images",
            font=(FONT_FAMILY, 10),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.counter_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = tk.Button(
            nav,
            text=">",
            font=(FONT_FAMILY, 12, "bold"),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=lambda: self._navigate(1),
            width=3,
            cursor="hand2",
            relief=tk.FLAT,
        )
        self.next_btn.pack(side=tk.RIGHT)

        # Info label (shows source type and filename)
        self.info_label = tk.Label(
            self,
            text="",
            font=(FONT_FAMILY, 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        )
        self.info_label.pack(fill=tk.X, padx=8, pady=(0, 5))

        # Listen for session changes
        self.image_session.set_on_change(self._on_session_change)

        # Bind canvas resize to redraw
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _on_session_change(self):
        """Called when image session state changes."""
        self._update_display()

    def _on_canvas_resize(self, _event=None):
        """Redraw on resize."""
        self._update_display()

    def _update_display(self):
        """Update the carousel display with current image."""
        self.canvas.delete("all")

        entry = self.image_session.active_entry
        count = self.image_session.count
        idx = self.image_session.current_index

        if count == 0:
            self.counter_label.config(text="No images")
            self.info_label.config(
                text="Add images to start the pipeline", fg=COLORS["text_dim"]
            )
            self.prev_btn.config(state=tk.DISABLED)
            self.next_btn.config(state=tk.DISABLED)
            return

        self.counter_label.config(text=f"{idx + 1} / {count}")
        self.prev_btn.config(state=tk.NORMAL if idx > 0 else tk.DISABLED)
        self.next_btn.config(
            state=tk.NORMAL if idx < count - 1 else tk.DISABLED
        )

        if entry:
            # Show source type badge with colour coding
            type_colors = {
                "input": COLORS["accent_blue"],
                "selfie": COLORS["success"],
                "outpaint": COLORS["warning"],
            }
            color = type_colors.get(entry.source_type, COLORS["text_dim"])
            self.info_label.config(
                text=f"[{entry.source_type.upper()}] {entry.filename}",
                fg=color,
            )

            if entry.exists:
                self._show_image(entry.path)
            else:
                cw = max(1, self.canvas.winfo_width())
                ch = max(1, self.canvas.winfo_height())
                self.canvas.create_text(
                    cw // 2,
                    ch // 2,
                    text="File not found",
                    fill=COLORS["error"],
                    font=(FONT_FAMILY, 12),
                )

    def _show_image(self, path: str):
        """Load and display an image on the canvas, fitted to canvas size."""
        try:
            from PIL import Image, ImageTk

            img = Image.open(path)
            cw = max(1, self.canvas.winfo_width() - 4)
            ch = max(1, self.canvas.winfo_height() - 4)

            # Fit to canvas maintaining aspect ratio
            ratio = min(cw / img.width, ch / img.height)
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            self._photo_ref = ImageTk.PhotoImage(img)
            self.canvas.create_image(
                cw // 2 + 2,
                ch // 2 + 2,
                image=self._photo_ref,
                anchor=tk.CENTER,
            )
        except ImportError:
            cw = max(1, self.canvas.winfo_width())
            ch = max(1, self.canvas.winfo_height())
            self.canvas.create_text(
                cw // 2,
                ch // 2,
                text="PIL not available",
                fill=COLORS["warning"],
                font=(FONT_FAMILY, 9),
            )
        except Exception as e:
            cw = max(1, self.canvas.winfo_width())
            ch = max(1, self.canvas.winfo_height())
            self.canvas.create_text(
                cw // 2,
                ch // 2,
                text=f"Cannot load: {e}",
                fill=COLORS["error"],
                font=(FONT_FAMILY, 9),
            )

    def _navigate(self, delta: int):
        """Navigate to a neighbouring image."""
        self.image_session.navigate(delta)

    def _on_add_image(self):
        """Open file dialog to add image(s) to session."""
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
