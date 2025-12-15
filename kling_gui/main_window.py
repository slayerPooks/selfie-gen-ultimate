"""
Main Window - Primary GUI window that assembles all components.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .drop_zone import DropZone, create_dnd_root, HAS_DND
from .log_display import LogDisplay
from .config_panel import ConfigPanel
from .queue_manager import QueueManager, QueueItem

# Try to import the generator
try:
    from kling_generator_falai import FalAIKlingGenerator
    HAS_GENERATOR = True
except ImportError:
    HAS_GENERATOR = False


# Color palette
COLORS = {
    "bg_main": "#2D2D30",
    "bg_panel": "#3C3C41",
    "bg_input": "#464649",
    "text_light": "#DCDCDC",
    "text_dim": "#B4B4B4",
    "accent_blue": "#6496FF",
    "success": "#64FF64",
    "error": "#FF6464",
    "warning": "#FFA500",
    "btn_green": "#329632",
    "btn_red": "#B43232",
}


class KlingGUIWindow:
    """Main GUI window for Kling video generation."""

    def __init__(self, config_path: str = "kling_config.json"):
        """
        Initialize the GUI window.

        Args:
            config_path: Path to the configuration JSON file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.history_path = Path(self.config_path).with_name("kling_history.json")
        self.history: List[dict] = self._load_history()
        self.generator: Optional[FalAIKlingGenerator] = None
        self.queue_manager: Optional[QueueManager] = None
        self.logger = self._setup_logging()

        # Create root window with DnD support if available
        self.root = create_dnd_root()
        self.root.title("FAL.AI Video Generator - GUI Mode")
        self.root.configure(bg=COLORS["bg_main"])
        self.root.geometry("900x850")
        self.root.minsize(700, 650)

        # Set up the UI
        self._setup_ui()

        # Initialize generator and queue manager
        self._init_generator()

        # Protocol for window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_logging(self) -> logging.Logger:
        """Configure rotating file logging."""
        log_dir = Path(self.config_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "kling_gui.log"

        logger = logging.getLogger("kling_gui")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            handler = RotatingFileHandler(
                log_file,
                maxBytes=int(self.config.get("log_max_mb", 5) * 1024 * 1024),
                backupCount=int(self.config.get("log_backups", 3)),
                encoding="utf-8"
            )
            fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            handler.setFormatter(fmt)
            logger.addHandler(handler)

        return logger

    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        default_config = {
            "output_folder": str(Path.home() / "Downloads"),
            "use_source_folder": True,
            "falai_api_key": "",
            "verbose_logging": True,
            "log_max_mb": 5,
            "log_backups": 3,
            "duplicate_detection": True,
            "current_prompt_slot": 1,
            "saved_prompts": {"1": "", "2": "", "3": ""},
            "negative_prompts": {"1": "", "2": "", "3": ""},
            "model_capabilities": {},
            "current_model": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
            "model_display_name": "Kling 2.5 Turbo Pro",
            "video_duration": 10,
            "loop_videos": False,
            "allow_reprocess": True,
            "reprocess_mode": "increment",
        }

        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    default_config.update(loaded)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")

        return default_config

    def _save_config(self):
        """Save configuration to JSON file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self._log(f"Error saving config: {e}", "error")

    def _load_history(self) -> List[dict]:
        """Load processed video history from disk."""
        try:
            if self.history_path.exists():
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            self._log(f"Could not load history: {e}", "warning")
        return []

    def _save_history(self):
        """Persist processed video history."""
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history[-500:], f, indent=2)
        except Exception as e:
            self._log(f"Could not save history: {e}", "warning")

    def _setup_ui(self):
        """Set up the main UI layout."""
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground=COLORS["bg_input"],
                       background=COLORS["bg_panel"], foreground=COLORS["text_light"])

        # Header
        self._setup_header()

        # Main content area
        main_frame = tk.Frame(self.root, bg=COLORS["bg_main"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Config panel at top
        self.config_panel = ConfigPanel(
            main_frame,
            config=self.config,
            on_config_changed=self._on_config_changed
        )
        self.config_panel.pack(fill=tk.X, pady=(0, 10))

        # Drop zone in the middle (fixed height, doesn't expand)
        self.drop_zone = DropZone(
            main_frame,
            on_files_dropped=self._on_files_dropped
        )
        self.drop_zone.pack(fill=tk.X, pady=(0, 10))
        self.drop_zone.config(height=200)
        self.drop_zone.pack_propagate(False)

        # Bottom section: Queue + Log side by side (gets remaining space)
        bottom_frame = tk.Frame(main_frame, bg=COLORS["bg_main"])
        bottom_frame.pack(fill=tk.BOTH, expand=True)

        # Queue panel (left)
        self._setup_queue_panel(bottom_frame)

        # Right side: Log + History
        right_frame = tk.Frame(bottom_frame, bg=COLORS["bg_main"])
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Log panel (top)
        self.log_display = LogDisplay(right_frame)
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 5))

        # History panel (bottom)
        self._setup_history_panel(right_frame)

        # Control buttons at bottom
        self._setup_controls()

    def _setup_header(self):
        """Set up the header bar."""
        header = tk.Frame(self.root, bg=COLORS["bg_panel"], height=40)
        header.pack(fill=tk.X, padx=10, pady=10)
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="🎬 FAL.AI VIDEO GENERATOR - GUI MODE",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"]
        )
        title.pack(side=tk.LEFT, padx=10, pady=8)

        # Balance link
        balance_link = tk.Label(
            header,
            text="💰 Check Balance",
            font=("Segoe UI", 9, "underline"),
            bg=COLORS["bg_panel"],
            fg=COLORS["accent_blue"],
            cursor="hand2"
        )
        balance_link.pack(side=tk.RIGHT, padx=10, pady=8)
        balance_link.bind("<Button-1>", lambda e: os.startfile("https://fal.ai/dashboard"))

        # DnD status
        dnd_status = "✓ Drag-Drop Enabled" if HAS_DND else "⚠ Drag-Drop Unavailable"
        dnd_color = COLORS["success"] if HAS_DND else COLORS["warning"]
        dnd_label = tk.Label(
            header,
            text=dnd_status,
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=dnd_color
        )
        dnd_label.pack(side=tk.RIGHT, padx=10, pady=8)

    def _setup_queue_panel(self, parent):
        """Set up the queue panel."""
        queue_frame = tk.Frame(parent, bg=COLORS["bg_panel"], width=280)
        queue_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        queue_frame.pack_propagate(False)

        # Header with count
        self.queue_header = tk.Label(
            queue_frame,
            text="📋 QUEUE (0/50)",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"]
        )
        self.queue_header.pack(fill=tk.X, padx=5, pady=(5, 2))

        # Queue listbox with scrollbar
        list_frame = tk.Frame(queue_frame, bg=COLORS["bg_main"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.queue_listbox = tk.Listbox(
            list_frame,
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            selectbackground=COLORS["accent_blue"],
            selectforeground="white",
            yscrollcommand=scrollbar.set,
            borderwidth=0,
            highlightthickness=0
        )
        self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.queue_listbox.yview)

        # Context menu for queue
        self.queue_menu = tk.Menu(self.queue_listbox, tearoff=0)
        self.queue_menu.add_command(label="Remove", command=self._remove_selected_item)
        self.queue_listbox.bind("<Button-3>", self._show_queue_menu)

    def _setup_history_panel(self, parent):
        """Processed videos history with open-in-explorer helpers."""
        panel = tk.Frame(parent, bg=COLORS["bg_panel"], height=220)
        panel.pack(fill=tk.X, padx=0, pady=(0, 0))
        panel.pack_propagate(False)

        header = tk.Frame(panel, bg=COLORS["bg_panel"])
        header.pack(fill=tk.X, padx=5, pady=(4, 2))

        tk.Label(
            header, text="🎞️ PROCESSED VIDEOS", font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_panel"], fg=COLORS["text_light"]
        ).pack(side=tk.LEFT)

        btn_frame = tk.Frame(header, bg=COLORS["bg_panel"])
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="Open File", command=self._open_selected_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Open Folder", command=self._open_selected_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_history_view).pack(side=tk.LEFT, padx=2)

        columns = ("time", "source", "output", "status")
        self.history_tree = ttk.Treeview(
            panel, columns=columns, show="headings", height=6, selectmode="browse"
        )
        for col, text, width in [
            ("time", "Time", 110),
            ("source", "Source", 180),
            ("output", "Output", 280),
            ("status", "Status", 90),
        ]:
            self.history_tree.heading(col, text=text)
            self.history_tree.column(col, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=(0, 5))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=(0, 5))

        self.history_tree.bind("<Double-1>", lambda e: self._open_selected_file())

        self._refresh_history_view()

    def _setup_controls(self):
        """Set up the control buttons."""
        control_frame = tk.Frame(self.root, bg=COLORS["bg_main"])
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Left side: Add file button (fallback if DnD unavailable)
        if not HAS_DND:
            add_btn = tk.Button(
                control_frame,
                text="📁 Add Files...",
                font=("Segoe UI", 10),
                bg=COLORS["btn_green"],
                fg="white",
                command=self._browse_files
            )
            add_btn.pack(side=tk.LEFT, padx=5)

        # Right side: Control buttons
        self.close_btn = tk.Button(
            control_frame,
            text="❌ Close",
            font=("Segoe UI", 10),
            bg=COLORS["btn_red"],
            fg="white",
            command=self._on_close
        )
        self.close_btn.pack(side=tk.RIGHT, padx=5)

        self.clear_btn = tk.Button(
            control_frame,
            text="🗑️ Clear",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._clear_queue
        )
        self.clear_btn.pack(side=tk.RIGHT, padx=5)

        self.retry_btn = tk.Button(
            control_frame,
            text="🔄 Retry Failed",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._retry_failed
        )
        self.retry_btn.pack(side=tk.RIGHT, padx=5)

        self.pause_btn = tk.Button(
            control_frame,
            text="⏸️ Pause",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._toggle_pause
        )
        self.pause_btn.pack(side=tk.RIGHT, padx=5)

    def _init_generator(self):
        """Initialize the video generator and queue manager."""
        if not HAS_GENERATOR:
            self._log("Generator not available - check kling_generator_falai.py", "error")
            return

        api_key = self.config.get("falai_api_key", "")
        if not api_key:
            self._log("No API key configured - set it in the main app first", "warning")
            return

        try:
            self.generator = FalAIKlingGenerator(
                api_key=api_key,
                verbose=self.config.get("verbose_logging", True),
                model_endpoint=self.config.get("current_model"),
                model_display_name=self.config.get("model_display_name")
            )

            self.queue_manager = QueueManager(
                generator=self.generator,
                config_getter=lambda: self.config,
                log_callback=self._log_thread_safe,
                queue_update_callback=self._update_queue_display_thread_safe,
                processing_complete_callback=self._on_item_complete
            )

            self._log("Generator initialized successfully", "success")

        except Exception as e:
            self._log(f"Failed to initialize generator: {e}", "error")

    def _log(self, message: str, level: str = "info"):
        """Log a message to the log display."""
        if hasattr(self, 'log_display'):
            self.log_display.log(message, level)
        if self.logger:
            level_map = {
                "info": self.logger.info,
                "success": self.logger.info,
                "warning": self.logger.warning,
                "error": self.logger.error,
            }
            level_map.get(level, self.logger.info)(message)

    def _log_thread_safe(self, message: str, level: str = "info"):
        """Thread-safe logging using after()."""
        self.root.after(0, lambda: self._log(message, level))

    def _update_queue_display(self):
        """Update the queue listbox display."""
        self.queue_listbox.delete(0, tk.END)

        if self.queue_manager:
            items = self.queue_manager.get_items()
            stats = self.queue_manager.get_stats()

            # Update header
            self.queue_header.config(
                text=f"📋 QUEUE ({stats['pending'] + stats['processing']}/50)"
            )

            # Add items to listbox
            for item in items:
                status_icon = {
                    "pending": "⏳",
                    "processing": "🔄",
                    "completed": "✅",
                    "failed": "❌"
                }.get(item.status, "?")

                display = f"{status_icon} {item.filename}"
                if item.status == "failed":
                    display += " [RETRY]"

                self.queue_listbox.insert(tk.END, display)

    def _update_queue_display_thread_safe(self):
        """Thread-safe queue display update."""
        self.root.after(0, self._update_queue_display)

    def _refresh_history_view(self):
        """Reload history tree from stored list."""
        if not hasattr(self, "history_tree"):
            return
        self.history_tree.delete(*self.history_tree.get_children())
        for entry in reversed(self.history[-200:]):  # show recent first
            status = entry.get("status", "")
            tag = "success" if status == "completed" else ("error" if status == "failed" else "")
            self.history_tree.insert(
                "", tk.END,
                values=(
                    entry.get("time", ""),
                    os.path.basename(entry.get("source", "")),
                    entry.get("output", ""),
                    status,
                ),
                tags=(tag,)
            )
        # color tags
        self.history_tree.tag_configure("success", foreground=COLORS["success"])
        self.history_tree.tag_configure("error", foreground=COLORS["error"])

    def _get_selected_history(self) -> Optional[dict]:
        if not hasattr(self, "history_tree"):
            return None
        sel = self.history_tree.selection()
        if not sel:
            return None
        # Tree shows reversed order; map index
        index = self.history_tree.index(sel[0])
        # reversed list so map back
        try:
            entry = list(reversed(self.history[-200:]))[index]
            return entry
        except Exception:
            return None

    def _open_selected_file(self):
        entry = self._get_selected_history()
        path = entry.get("output") if entry else None
        if path and os.path.exists(path):
            os.startfile(path)
        elif entry and entry.get("output"):
            self._log(f"File not found: {entry['output']}", "warning")

    def _open_selected_folder(self):
        entry = self._get_selected_history()
        path = None
        if entry:
            path = entry.get("output") or entry.get("source")
        if path:
            folder = os.path.dirname(path)
            if folder and os.path.exists(folder):
                os.startfile(folder)
                return
        self._log("No folder to open for selection", "warning")

    def _on_files_dropped(self, files: List[str]):
        """Handle files dropped onto the drop zone."""
        if not self.queue_manager:
            self._log("Queue manager not initialized", "error")
            return

        added = 0
        for file_path in files:
            success, message = self.queue_manager.add_to_queue(file_path)
            if success:
                added += 1
            else:
                self._log(f"Skipped: {os.path.basename(file_path)} - {message}", "warning")

        if added > 0:
            self._log(f"Added {added} file(s) to queue", "success")

    def _on_config_changed(self, new_config: dict):
        """Handle configuration changes from the config panel."""
        self.config.update(new_config)
        self._save_config()

        # Update generator if model changed
        if self.generator:
            model = new_config.get("current_model")
            if model and model != self.generator.base_url.split("/")[-1]:
                self._log(f"Model changed - will apply to next item", "info")

    def _on_item_complete(self, item: QueueItem):
        """Called when an item finishes processing."""
        status = item.status
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "time": timestamp,
            "source": item.path,
            "output": item.output_path or "",
            "status": status,
            "error": item.error_message or "",
        }
        self.history.append(entry)
        # Keep history reasonably sized
        self.history = self.history[-500:]
        self._save_history()
        self._refresh_history_view()

        if status == "completed" and item.output_path:
            self._log(f"Finished {os.path.basename(item.path)} → {item.output_path}", "success")
        elif status == "failed":
            self._log(f"Failed {os.path.basename(item.path)}: {item.error_message}", "error")

    def _toggle_pause(self):
        """Toggle pause/resume."""
        if not self.queue_manager:
            return

        if self.queue_manager.is_paused:
            self.queue_manager.resume_processing()
            self.pause_btn.config(text="⏸️ Pause")
        else:
            self.queue_manager.pause_processing()
            self.pause_btn.config(text="▶️ Resume")

    def _retry_failed(self):
        """Retry all failed items."""
        if self.queue_manager:
            count = self.queue_manager.retry_failed()
            if count == 0:
                self._log("No failed items to retry", "info")

    def _clear_queue(self):
        """Clear the queue."""
        if self.queue_manager:
            self.queue_manager.clear_queue()

    def _remove_selected_item(self):
        """Remove the selected item from the queue."""
        selection = self.queue_listbox.curselection()
        if selection and self.queue_manager:
            self.queue_manager.remove_item(selection[0])

    def _show_queue_menu(self, event):
        """Show context menu for queue item."""
        try:
            self.queue_listbox.selection_clear(0, tk.END)
            self.queue_listbox.selection_set(self.queue_listbox.nearest(event.y))
            self.queue_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.queue_menu.grab_release()

    def _browse_files(self):
        """Open file browser to add files (fallback for no DnD)."""
        files = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff *.tif"),
                ("All files", "*.*")
            ]
        )
        if files:
            self._on_files_dropped(list(files))

    def _on_close(self):
        """Handle window close."""
        if self.queue_manager and self.queue_manager.is_running:
            if not messagebox.askyesno(
                "Confirm Close",
                "Processing is in progress. Are you sure you want to close?"
            ):
                return

            self.queue_manager.stop_processing()

        self._save_history()
        self._save_config()
        self.root.destroy()

    def run(self):
        """Run the GUI main loop."""
        self._log("GUI started - drag images to process", "info")
        self.root.mainloop()


def launch_gui(config_path: str = "kling_config.json"):
    """Launch the GUI window."""
    window = KlingGUIWindow(config_path=config_path)
    window.run()


if __name__ == "__main__":
    launch_gui()
