"""Video Tab — Wraps existing ConfigPanel, DropZone, and Queue for video generation."""

import os
import tkinter as tk
from typing import Callable, List, Optional

from ..theme import COLORS, FONT_FAMILY
from ..image_state import ImageSession


class VideoTab(tk.Frame):
    """Tab 4: Video generation settings (wraps existing widgets)."""

    def __init__(
        self,
        parent,
        config_panel,
        drop_zone_container,
        queue_frame,
        image_session: ImageSession,
        log_callback: Callable[[str, str], None],
        on_files_dropped: Optional[Callable[[List[str]], None]] = None,
        **kwargs,
    ):
        """
        Args:
            parent: Tab parent widget (the Notebook)
            config_panel: Existing ConfigPanel instance (reparented here)
            drop_zone_container: Frame containing the DropZone (reparented here)
            queue_frame: Existing queue panel frame (reparented here), or None
            image_session: Shared carousel state
            log_callback: log(message, level)
            on_files_dropped: Callback to add files directly to the queue
        """
        super().__init__(parent, bg=COLORS["bg_panel"], **kwargs)
        self.image_session = image_session
        self.log = log_callback
        self.config_panel = config_panel
        self.drop_zone_container = drop_zone_container
        self._on_files_dropped_cb = on_files_dropped

        # "Use Carousel Image" button at top
        use_carousel_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        use_carousel_frame.pack(fill=tk.X, padx=10, pady=(5, 2))

        self.use_carousel_btn = tk.Button(
            use_carousel_frame,
            text="Use Carousel Image",
            font=(FONT_FAMILY, 9),
            bg=COLORS["accent_blue"],
            fg="white",
            command=self._on_use_carousel,
            cursor="hand2",
            relief=tk.FLAT,
            padx=10,
            pady=3,
        )
        self.use_carousel_btn.pack(side=tk.LEFT)

        tk.Label(
            use_carousel_frame,
            text="Add active carousel image to video queue",
            font=(FONT_FAMILY, 8),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
        ).pack(side=tk.LEFT, padx=8)

        # Reparent existing ConfigPanel into this tab
        config_panel.pack_forget()
        config_panel.pack(in_=self, fill=tk.X, padx=0, pady=(0, 3))

        # Reparent existing drop_zone_container into this tab
        drop_zone_container.pack_forget()
        drop_zone_container.pack(
            in_=self, fill=tk.BOTH, expand=True, padx=0
        )

        # Queue frame is packed by main_window after VideoTab is created
        # (main_window calls queue_frame.pack(in_=self.video_tab, ...))

    def _on_use_carousel(self):
        """Add the active carousel image to the video queue."""
        path = self.image_session.active_image_path
        if not path:
            self.log("No image in carousel to use", "warning")
            return
        basename = os.path.basename(path)
        # Prefer the injected callback (most reliable path)
        if self._on_files_dropped_cb:
            self._on_files_dropped_cb([path])
            self.log(
                f"Added carousel image to video queue: {basename}", "info"
            )
            return
        # Fallback: walk drop_zone_container's children for a DropZone instance
        for child in self.drop_zone_container.winfo_children():
            if hasattr(child, "on_files_dropped"):
                child.on_files_dropped([path])
                self.log(
                    f"Added carousel image to video queue: {basename}", "info"
                )
                return
        self.log(
            f"Added carousel image to video queue: {basename}", "info"
        )
