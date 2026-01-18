"""
Main Window - Primary GUI window that assembles all components.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import os
import sys
import logging
from copy import deepcopy
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

# Import path utilities
from path_utils import get_config_path, get_crash_log_path, get_log_path, get_app_dir

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
    if TYPE_CHECKING:
        from kling_generator_falai import FalAIKlingGenerator


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

# Valid image extensions for folder scanning
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}


UI_CONFIG_DEFAULTS = {
    "window": {"width": 1100, "height": 1200, "min_width": 800, "min_height": 900},
    "config_panel": {
        "prompt_preview_height": 6,
        "prompt_preview_font_size": 9,
        "negative_prompt_height": 1,
    },
    "drop_zone": {"height": 180},
    "queue_panel": {"width": 300},
    "history_panel": {"height": 220, "visible_rows": 8},
    "debug": {"enabled": False, "inspector_hotkey": "F12", "reload_hotkey": "F5"},
}


class FolderPreviewDialog(tk.Toplevel):
    """Dialog showing matched files before adding to queue."""

    def __init__(
        self, parent, files: List[str], folder: str, pattern: str, match_mode: str
    ):
        super().__init__(parent)
        self.title("Folder Processing Preview")
        self.result = None  # True = proceed, None = cancel
        self.files = files

        # Modal
        self.transient(parent)
        self.grab_set()
        self.configure(bg=COLORS["bg_panel"])
        self.geometry("700x550")
        self.minsize(500, 400)

        # Header
        tk.Label(
            self,
            text=f"Found {len(files)} matching images",
            font=("Segoe UI", 14, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(pady=(15, 5))

        # Info frame
        info_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        info_frame.pack(fill=tk.X, padx=20)

        tk.Label(
            info_frame,
            text=f"Folder: {folder}",
            font=("Segoe UI", 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_dim"],
            anchor="w",
        ).pack(fill=tk.X)

        mode_text = "exact name" if match_mode == "exact" else "contains"
        tk.Label(
            info_frame,
            text=f"Pattern: '{pattern}' ({mode_text})",
            font=("Segoe UI", 9),
            bg=COLORS["bg_panel"],
            fg=COLORS["accent_blue"],
            anchor="w",
        ).pack(fill=tk.X)

        # File list with scrollbar
        list_frame = tk.Frame(self, bg=COLORS["bg_main"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_list = tk.Listbox(
            list_frame,
            bg=COLORS["bg_main"],
            fg=COLORS["text_light"],
            font=("Consolas", 9),
            selectbackground=COLORS["accent_blue"],
            yscrollcommand=scrollbar.set,
            borderwidth=0,
            highlightthickness=0,
        )
        self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_list.yview)

        # Populate list (show relative paths)
        for f in files:
            try:
                rel_path = os.path.relpath(f, folder)
            except ValueError:
                rel_path = os.path.basename(f)
            self.file_list.insert(tk.END, rel_path)

        # Buttons
        btn_frame = tk.Frame(self, bg=COLORS["bg_panel"])
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

        tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            width=12,
            command=self._cancel,
        ).pack(side=tk.RIGHT, padx=5)

        tk.Button(
            btn_frame,
            text=f"Add {len(files)} to Queue",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["btn_green"],
            fg="white",
            width=18,
            command=self._proceed,
        ).pack(side=tk.RIGHT, padx=5)

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 550) // 2
        self.geometry(f"+{x}+{y}")

        self.wait_window()

    def _proceed(self):
        self.result = True
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class KlingGUIWindow:
    """Main GUI window for Kling video generation."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the GUI window.

        Args:
            config_path: Path to the configuration JSON file (defaults to app dir)
        """
        # Use get_config_path for proper frozen exe compatibility
        if config_path is None:
            self.config_path = get_config_path("kling_config.json")
        elif os.path.isabs(config_path):
            self.config_path = config_path
        else:
            # Relative path - make it relative to app dir
            self.config_path = os.path.join(get_app_dir(), config_path)

        self.config = self._load_config()
        self.ui_config_path = os.path.join(get_app_dir(), "ui_config.json")
        self.ui_config = self._load_ui_config()
        self.edit_mode = False
        self.dimension_labels = {}
        # History file in same directory as config
        self.history_path = os.path.join(
            os.path.dirname(self.config_path), "kling_history.json"
        )

        # Set up logging BEFORE anything that might call _log()
        self.logger = self._setup_logging()

        self.history: List[dict] = self._load_history()
        self.generator: Optional["FalAIKlingGenerator"] = None
        self.queue_manager: Optional[QueueManager] = None

        # Create root window with DnD support if available
        self.root = create_dnd_root()
        self.root.title("FAL.AI Video Generator - GUI Mode")
        self.root.configure(bg=COLORS["bg_main"])

        # Restore window geometry or use defaults
        window_config = self.ui_config.get("window", {})
        try:
            window_width = int(window_config.get("width", 1100))
            window_height = int(window_config.get("height", 1200))
            min_width = int(window_config.get("min_width", 800))
            min_height = int(window_config.get("min_height", 900))
        except (TypeError, ValueError):
            window_width, window_height, min_width, min_height = 1100, 1200, 800, 900

        saved_geometry = self.config.get("window_geometry", "")
        if saved_geometry:
            try:
                self.root.geometry(saved_geometry)
            except Exception:
                self.root.geometry(f"{window_width}x{window_height}")
        else:
            self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(min_width, min_height)

        # Set up the UI
        self._setup_ui()

        # Restore sash positions after UI is built (delayed to ensure widgets are ready)
        self.root.after(100, self._restore_sash_positions)
        self.root.after(150, self._apply_ui_config)

        # Enable debug hotkeys/inspector if configured
        self._setup_debug_hotkeys()

        # Initialize generator and queue manager
        self._init_generator()

        # Protocol for window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_logging(self) -> logging.Logger:
        """Configure rotating file logging."""
        # Use get_log_path for proper frozen exe compatibility
        log_file = get_log_path("kling_gui.log")

        logger = logging.getLogger("kling_gui")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            handler = RotatingFileHandler(
                log_file,
                maxBytes=int(self.config.get("log_max_mb", 5) * 1024 * 1024),
                backupCount=int(self.config.get("log_backups", 3)),
                encoding="utf-8",
            )
            fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            handler.setFormatter(fmt)
            logger.addHandler(handler)

        return logger

    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        default_config = {
            "output_folder": "",  # Empty by default - user picks their own
            "use_source_folder": True,
            "falai_api_key": "",
            "verbose_logging": True,
            "verbose_gui_mode": True,  # Verbose GUI logging ON by default
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
            "loop_videos": True,  # Loop videos ON by default
            "allow_reprocess": True,
            "reprocess_mode": "increment",
            # Folder processing settings
            "folder_filter_pattern": "",
            "folder_match_mode": "partial",  # "partial" or "exact"
            # Window layout persistence
            "window_geometry": "",  # Empty = use default
            "sash_dropzone": 180,  # Height of drop zone pane
            "sash_queue": 300,  # Width of queue pane
            "sash_log": 380,  # Height of log pane (before history)
        }

        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with defaults
                    default_config.update(loaded)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")

        return default_config

    def _merge_ui_config(self, base: dict, updates: dict) -> dict:
        """Deep-merge UI config dictionaries."""
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._merge_ui_config(base[key], value)
            else:
                base[key] = value
        return base

    def _load_ui_config(self) -> dict:
        """Load UI layout configuration from ui_config.json."""
        config = deepcopy(UI_CONFIG_DEFAULTS)
        try:
            if self.ui_config_path and os.path.exists(self.ui_config_path):
                with open(self.ui_config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self._merge_ui_config(config, loaded)
        except Exception as e:
            print(f"Warning: Could not load UI config: {e}")
        return config

    def _save_config(self):
        """Save configuration to JSON file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self._log(f"Error saving config: {e}", "error")

    def _load_history(self) -> List[dict]:
        """Load processed video history from disk."""
        try:
            if os.path.exists(self.history_path):
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
        """Set up the main UI layout with resizable panes."""
        # Style configuration
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["bg_input"],
            background=COLORS["bg_panel"],
            foreground=COLORS["text_light"],
        )

        # Dark theme for Treeview (PROCESSED VIDEOS section)
        style.configure(
            "Treeview",
            background=COLORS["bg_panel"],
            foreground=COLORS["text_light"],
            fieldbackground=COLORS["bg_panel"],
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["bg_input"],
            foreground=COLORS["text_light"],
            borderwidth=1,
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["accent_blue"])],
            foreground=[("selected", "white")],
        )

        # Dark theme for PanedWindow sash (drag handles)
        style.configure("TPanedwindow", background=COLORS["bg_main"])
        style.configure("Sash", sashthickness=6, sashrelief=tk.FLAT)

        # Header
        self._setup_header()

        # Main content area
        main_frame = tk.Frame(self.root, bg=COLORS["bg_main"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Config panel at top (not resizable)
        self.config_panel = ConfigPanel(
            main_frame, config=self.config, on_config_changed=self._on_config_changed
        )
        self.config_panel.pack(fill=tk.X, pady=(0, 5))

        # Main vertical PanedWindow: Drop Zone | Bottom Section
        self.main_paned = tk.PanedWindow(
            main_frame,
            orient=tk.VERTICAL,
            bg=COLORS["bg_input"],
            sashwidth=6,
            sashrelief=tk.RAISED,
            sashpad=1,
        )
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # Drop zone pane (top)
        drop_frame = tk.Frame(self.main_paned, bg=COLORS["bg_main"])
        self.drop_zone = DropZone(
            drop_frame,
            on_files_dropped=self._on_files_dropped,
            on_folder_dropped=self._on_folder_dropped,
        )
        self.drop_zone.pack(fill=tk.BOTH, expand=True)
        self.main_paned.add(drop_frame, minsize=100)

        # Bottom section: Horizontal PanedWindow (Queue | Log+History)
        self.bottom_paned = tk.PanedWindow(
            self.main_paned,
            orient=tk.HORIZONTAL,
            bg=COLORS["bg_input"],
            sashwidth=6,
            sashrelief=tk.RAISED,
            sashpad=1,
        )
        self.main_paned.add(self.bottom_paned, minsize=200)

        # Queue panel (left pane)
        self.queue_frame = tk.Frame(self.bottom_paned, bg=COLORS["bg_panel"])
        self._setup_queue_panel_content(self.queue_frame)
        self.bottom_paned.add(self.queue_frame, minsize=150)

        # Right side: Vertical PanedWindow (Log | History)
        self.right_paned = tk.PanedWindow(
            self.bottom_paned,
            orient=tk.VERTICAL,
            bg=COLORS["bg_input"],
            sashwidth=6,
            sashrelief=tk.RAISED,
            sashpad=1,
        )
        self.bottom_paned.add(self.right_paned, minsize=200)

        # Log panel (top right pane)
        log_frame = tk.Frame(self.right_paned, bg=COLORS["bg_main"])
        self.log_display = LogDisplay(log_frame)
        self.log_display.pack(fill=tk.BOTH, expand=True)
        self.right_paned.add(log_frame, minsize=100)

        # History panel (bottom right pane)
        self.history_frame = tk.Frame(self.right_paned, bg=COLORS["bg_panel"])
        self._setup_history_panel_content(self.history_frame)
        self.right_paned.add(self.history_frame, minsize=100)

        # Control buttons at bottom
        self._setup_controls()

    def _apply_ui_config(self):
        """Apply UI layout configuration to existing widgets."""
        if not hasattr(self, "root"):
            return

        window_config = self.ui_config.get("window", {})
        try:
            width = int(window_config.get("width", 1100))
            height = int(window_config.get("height", 1200))
            min_width = int(window_config.get("min_width", 800))
            min_height = int(window_config.get("min_height", 900))
        except (TypeError, ValueError):
            width, height, min_width, min_height = 1100, 1200, 800, 900

        try:
            self.root.minsize(min_width, min_height)
        except Exception:
            pass

        try:
            current_geom = self.root.geometry()
            x_pos = None
            y_pos = None
            if "+" in current_geom:
                parts = current_geom.split("+")
                if len(parts) >= 3:
                    x_pos = parts[1]
                    y_pos = parts[2]
            if x_pos is not None and y_pos is not None:
                self.root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
            else:
                self.root.geometry(f"{width}x{height}")
        except Exception:
            pass

        if hasattr(self, "config_panel") and hasattr(self.config_panel, "apply_ui_config"):
            self.config_panel.apply_ui_config(self.ui_config)

        try:
            drop_height = int(self.ui_config.get("drop_zone", {}).get("height", 180))
            queue_width = int(self.ui_config.get("queue_panel", {}).get("width", 300))
            history_height = int(
                self.ui_config.get("history_panel", {}).get("height", 220)
            )
        except (TypeError, ValueError):
            drop_height, queue_width, history_height = 180, 300, 220

        sash_positions = self.ui_config.get("sash_positions", {})
        log_sash_y = None
        try:
            if "dropzone" in sash_positions:
                drop_value = sash_positions.get("dropzone")
                if isinstance(drop_value, (list, tuple)) and len(drop_value) >= 2:
                    drop_height = int(drop_value[1])
                else:
                    drop_height = int(drop_value)
        except (TypeError, ValueError):
            pass

        try:
            if "queue" in sash_positions:
                queue_value = sash_positions.get("queue")
                if isinstance(queue_value, (list, tuple)) and len(queue_value) >= 1:
                    queue_width = int(queue_value[0])
                else:
                    queue_width = int(queue_value)
        except (TypeError, ValueError):
            pass

        try:
            if "log" in sash_positions:
                log_value = sash_positions.get("log")
                if isinstance(log_value, (list, tuple)) and len(log_value) >= 2:
                    log_sash_y = int(log_value[1])
        except (TypeError, ValueError):
            pass

        try:
            visible_rows = int(
                self.ui_config.get("history_panel", {}).get("visible_rows", 8)
            )
        except (TypeError, ValueError):
            visible_rows = 8

        self.root.update_idletasks()

        if hasattr(self, "main_paned"):
            try:
                self.main_paned.sash_place(0, 0, drop_height)
            except Exception:
                pass

        if hasattr(self, "bottom_paned"):
            try:
                self.bottom_paned.sash_place(0, queue_width, 0)
            except Exception:
                pass

        if hasattr(self, "right_paned"):
            try:
                total_height = self.right_paned.winfo_height()
                if total_height > 0:
                    if log_sash_y is not None:
                        self.right_paned.sash_place(0, 0, log_sash_y)
                    else:
                        log_height = max(50, total_height - history_height)
                        self.right_paned.sash_place(0, 0, log_height)
            except Exception:
                pass

        if hasattr(self, "history_tree"):
            try:
                self.history_tree.config(height=max(1, visible_rows))
            except Exception:
                pass

    def _setup_debug_hotkeys(self):
        """Bind debug hotkeys and inspector, when enabled in ui_config.json."""
        debug_config = self.ui_config.get("debug", {})
        self._debug_enabled = bool(debug_config.get("enabled", False))
        if not self._debug_enabled:
            return

        inspector_hotkey = debug_config.get("inspector_hotkey", "F12")
        reload_hotkey = debug_config.get("reload_hotkey", "F5")

        try:
            # Unbind existing hotkeys to prevent duplication on reload
            self.root.unbind(f"<{inspector_hotkey}>")
            self.root.unbind(f"<{reload_hotkey}>")
            self.root.unbind("<Control-e>")
            self.root.unbind("<Control-s>")
            # Note: bind_all can't be easily unbound without tracking, 
            # but Button-3 with add="+" won't cause issues
            
            # Rebind hotkeys
            self.root.bind(
                f"<{inspector_hotkey}>", lambda e: self._dump_widget_tree()
            )
            self.root.bind(f"<{reload_hotkey}>", lambda e: self._hot_reload_ui())
            self.root.bind_all("<Button-3>", self._inspect_widget, add="+")
            self.root.bind("<Control-e>", lambda e: self._toggle_edit_mode())
            self.root.bind("<Control-s>", lambda e: self._export_current_layout())
        except Exception:
            pass

        try:
            if hasattr(self, "main_paned"):
                self.main_paned.bind("<B1-Motion>", self._on_sash_drag, add="+")
            if hasattr(self, "bottom_paned"):
                self.bottom_paned.bind("<B1-Motion>", self._on_sash_drag, add="+")
            if hasattr(self, "right_paned"):
                self.right_paned.bind("<B1-Motion>", self._on_sash_drag, add="+")
        except Exception:
            pass

        self._log(
            "UI debug hotkeys enabled (F12 tree, F5 reload, Ctrl+E edit, Ctrl+S export)",
            "info",
        )

    def _dump_widget_tree(self, widget=None, indent=0):
        """Print widget hierarchy with sizes."""
        if not getattr(self, "_debug_enabled", False):
            return
        if widget is None:
            widget = self.root
            print("\n=== WIDGET TREE ===")

        name = str(widget)
        size = f"{widget.winfo_width()}x{widget.winfo_height()}"
        req = f"{widget.winfo_reqwidth()}x{widget.winfo_reqheight()}"
        manager = widget.winfo_manager()
        print(
            "  " * indent
            + f"{widget.__class__.__name__} {name} - {size} (req {req}) [{manager}]"
        )

        try:
            if manager == "pack":
                print("  " * (indent + 1) + f"pack: {widget.pack_info()}")
            elif manager == "grid":
                print("  " * (indent + 1) + f"grid: {widget.grid_info()}")
            elif manager == "place":
                print("  " * (indent + 1) + f"place: {widget.place_info()}")
        except Exception:
            pass

        for child in widget.winfo_children():
            self._dump_widget_tree(child, indent + 1)

    def _inspect_widget(self, event):
        """Right-click inspector."""
        if not getattr(self, "_debug_enabled", False):
            return

        w = event.widget
        self._flash_widget_border(w)
        widget_path = self._get_widget_path(w)

        info_lines = [
            f"Path: {widget_path}",
            f"Class: {w.__class__.__name__} {str(w)}",
            f"Size: {w.winfo_width()} x {w.winfo_height()} (req {w.winfo_reqwidth()} x {w.winfo_reqheight()})",
            f"Position: ({w.winfo_x()}, {w.winfo_y()}) in parent",
            f"Screen: ({w.winfo_rootx()}, {w.winfo_rooty()})",
            f"Manager: {w.winfo_manager()}",
        ]

        try:
            manager = w.winfo_manager()
            if manager == "pack":
                info_lines.append(f"Pack: {w.pack_info()}")
            elif manager == "grid":
                info_lines.append(f"Grid: {w.grid_info()}")
            elif manager == "place":
                info_lines.append(f"Place: {w.place_info()}")
        except Exception:
            pass

        print("\n=== WIDGET INSPECTOR ===")
        for line in info_lines:
            print(line)

        self._show_inspector_popup(info_lines, event.x_root, event.y_root)

    def _get_widget_path(self, widget) -> str:
        """Get full widget hierarchy path."""
        path = []
        current = widget
        while current is not None:
            name = current.__class__.__name__
            if hasattr(current, "_name"):
                name = f"{name}({current._name})"
            path.insert(0, name)
            current = current.master if hasattr(current, "master") else None
        return " -> ".join(path)

    def _flash_widget_border(self, widget):
        """Flash a red border around a widget to highlight it."""
        try:
            original_thickness = widget.cget("highlightthickness")
            original_color = widget.cget("highlightbackground")
            widget.config(highlightthickness=3, highlightbackground="#FF4040")

            def restore():
                widget.config(
                    highlightthickness=original_thickness,
                    highlightbackground=original_color,
                )

            self.root.after(400, restore)
        except Exception:
            pass

    def _toggle_edit_mode(self):
        """Ctrl+E: Toggle layout edit mode."""
        self.edit_mode = not self.edit_mode
        if self.edit_mode:
            self._log("LAYOUT EDIT MODE - Drag panels, Ctrl+S to export", "warning")
            self._show_all_dimensions()
        else:
            self._log("Edit mode disabled", "info")
            self._hide_dimension_overlays()

    def _show_all_dimensions(self):
        """Show dimension overlays on major widgets."""
        self._hide_dimension_overlays()
        widgets_to_track = [
            ("Window", self.root),
            ("Config Panel", self.config_panel if hasattr(self, "config_panel") else None),
            ("Drop Zone", self.drop_zone if hasattr(self, "drop_zone") else None),
            ("Queue Panel", self.queue_frame if hasattr(self, "queue_frame") else None),
            ("Log Display", self.log_display if hasattr(self, "log_display") else None),
            (
                "History Panel",
                self.history_frame if hasattr(self, "history_frame") else None,
            ),
        ]

        print("\n" + "=" * 50)
        print("CURRENT LAYOUT DIMENSIONS")
        print("=" * 50)

        for name, widget in widgets_to_track:
            if not widget:
                continue
            width = widget.winfo_width()
            height = widget.winfo_height()
            print(f"{name:20} {width:4} x {height:4}")

            label = tk.Label(
                widget,
                text=f"{width}x{height}",
                font=("Segoe UI", 9, "bold"),
                bg="#E53935",
                fg="white",
                padx=4,
                pady=2,
            )
            label.place(relx=1.0, rely=0.0, anchor="ne")
            self.dimension_labels[name] = label

        self._print_sash_positions()
        print("=" * 50 + "\n")

    def _hide_dimension_overlays(self):
        """Remove all dimension overlay labels."""
        for label in self.dimension_labels.values():
            try:
                label.destroy()
            except Exception:
                pass
        self.dimension_labels.clear()

    def _on_sash_drag(self, event):
        """Update dimension display during sash drag."""
        if not self.edit_mode:
            return

        if getattr(self, "_sash_update_pending", False):
            return

        self._sash_update_pending = True

        def update():
            self._print_sash_positions()
            self._update_dimension_overlays()
            self._sash_update_pending = False

        self.root.after(100, update)

    def _update_dimension_overlays(self):
        """Refresh overlay labels with current sizes."""
        if not self.edit_mode:
            return

        mapping = {
            "Window": self.root,
            "Config Panel": getattr(self, "config_panel", None),
            "Drop Zone": getattr(self, "drop_zone", None),
            "Queue Panel": getattr(self, "queue_frame", None),
            "Log Display": getattr(self, "log_display", None),
            "History Panel": getattr(self, "history_frame", None),
        }

        for name, widget in mapping.items():
            if not widget:
                continue
            label = self.dimension_labels.get(name)
            if not label:
                continue
            label.config(text=f"{widget.winfo_width()}x{widget.winfo_height()}")

    def _print_sash_positions(self):
        """Print current sash positions."""
        positions = {}
        try:
            if hasattr(self, "main_paned"):
                positions["dropzone_sash"] = self.main_paned.sash_coord(0)
        except Exception:
            pass

        try:
            if hasattr(self, "bottom_paned"):
                positions["queue_sash"] = self.bottom_paned.sash_coord(0)
        except Exception:
            pass

        try:
            if hasattr(self, "right_paned"):
                positions["log_sash"] = self.right_paned.sash_coord(0)
        except Exception:
            pass

        if positions:
            self._show_sash_toast(positions)

    def _show_sash_toast(self, positions: dict):
        """Show a short-lived overlay with current sash positions."""
        if not self.edit_mode:
            return

        try:
            if hasattr(self, "_sash_toast") and self._sash_toast.winfo_exists():
                self._sash_toast.destroy()
        except Exception:
            pass

        try:
            popup = tk.Toplevel(self.root)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)
            try:
                popup.attributes("-alpha", 0.85)
            except Exception:
                pass

            text = (
                f"Drop: {positions.get('dropzone_sash', '')}  |  "
                f"Queue: {positions.get('queue_sash', '')}  |  "
                f"Log: {positions.get('log_sash', '')}"
            )

            frame = tk.Frame(popup, bg="#202225", bd=1, relief=tk.SOLID)
            frame.pack(fill=tk.BOTH, expand=True)

            label = tk.Label(
                frame,
                text=text,
                font=("Consolas", 9, "bold"),
                bg="#202225",
                fg="#F2F2F2",
                padx=10,
                pady=6,
            )
            label.pack()

            self.root.update_idletasks()
            popup.update_idletasks()

            root_x = self.root.winfo_rootx()
            root_y = self.root.winfo_rooty()
            root_w = self.root.winfo_width()
            root_h = self.root.winfo_height()
            toast_w = popup.winfo_reqwidth()
            toast_h = popup.winfo_reqheight()

            margin = 12
            x = root_x + max(0, root_w - toast_w - margin)
            y = root_y + max(0, root_h - toast_h - margin)
            popup.geometry(f"+{x}+{y}")

            popup.after(1000, popup.destroy)
            self._sash_toast = popup
        except Exception:
            pass

    def _export_current_layout(self):
        """Ctrl+S: Export current layout to JSON."""
        try:
            layout = {
                "_comment": "Exported layout - copy values to ui_config.json",
                "window": {
                    "width": self.root.winfo_width(),
                    "height": self.root.winfo_height(),
                    "min_width": self.root.winfo_width(),
                    "min_height": self.root.winfo_height(),
                },
                "config_panel": {
                    "prompt_preview_height": (
                        int(self.config_panel.prompt_preview.cget("height"))
                        if hasattr(self, "config_panel")
                        and hasattr(self.config_panel, "prompt_preview")
                        else 0
                    ),
                    "prompt_preview_font_size": 9,
                    "negative_prompt_height": 1,
                    "prompt_preview_width": (
                        self.config_panel.prompt_preview_container.winfo_width()
                        if hasattr(self, "config_panel")
                        and hasattr(self.config_panel, "prompt_preview_container")
                        else 0
                    ),
                    "prompt_preview_right_pad": 0,
                    "prompt_preview_offset_x": 16,
                },
                "drop_zone": {
                    "height": self.drop_zone.winfo_height()
                    if hasattr(self, "drop_zone")
                    else 0
                },
                "queue_panel": {
                    "width": self.queue_frame.winfo_width()
                    if hasattr(self, "queue_frame")
                    else 0
                },
                "history_panel": {
                    "height": self.history_frame.winfo_height()
                    if hasattr(self, "history_frame")
                    else 0,
                    "visible_rows": (
                        int(self.history_tree.cget("height"))
                        if hasattr(self, "history_tree")
                        else 0
                    ),
                },
                "sash_positions": {},
            }

            try:
                if hasattr(self, "main_paned"):
                    layout["sash_positions"]["dropzone"] = self.main_paned.sash_coord(0)
            except Exception:
                pass

            try:
                if hasattr(self, "bottom_paned"):
                    layout["sash_positions"]["queue"] = self.bottom_paned.sash_coord(0)
            except Exception:
                pass

            try:
                if hasattr(self, "right_paned"):
                    layout["sash_positions"]["log"] = self.right_paned.sash_coord(0)
            except Exception:
                pass

            export_path = Path("ui_config_exported.json")
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(layout, f, indent=2)

            self._log(
                f"Layout exported to {export_path.name}",
                "success",
            )
            print(f"\nExported to: {export_path.absolute()}")
            print(json.dumps(layout, indent=2))
        except Exception as e:
            self._log(f"Export failed: {e}", "error")

    def _show_inspector_popup(self, lines: List[str], x: int, y: int):
        """Show an on-screen tooltip with widget details."""
        try:
            if hasattr(self, "_inspector_popup") and self._inspector_popup.winfo_exists():
                self._inspector_popup.destroy()
        except Exception:
            pass

        try:
            popup = tk.Toplevel(self.root)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)

            frame = tk.Frame(popup, bg=COLORS["bg_panel"], bd=1, relief=tk.SOLID)
            frame.pack(fill=tk.BOTH, expand=True)

            for line in lines:
                tk.Label(
                    frame,
                    text=line,
                    font=("Consolas", 8),
                    bg=COLORS["bg_panel"],
                    fg=COLORS["text_light"],
                    anchor="w",
                ).pack(fill=tk.X, padx=6, pady=1)

            popup.geometry(f"+{x + 10}+{y + 10}")
            popup.after(2000, popup.destroy)
            self._inspector_popup = popup
        except Exception:
            pass

    def _hot_reload_ui(self):
        """F5 to reload UI config."""
        self.ui_config = self._load_ui_config()
        self._apply_ui_config()
        self._setup_debug_hotkeys()
        self._log("UI reloaded from ui_config.json", "success")

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
            fg=COLORS["text_light"],
        )
        title.pack(side=tk.LEFT, padx=10, pady=8)

        # Balance link
        balance_link = tk.Label(
            header,
            text="💰 Check Balance",
            font=("Segoe UI", 9, "underline"),
            bg=COLORS["bg_panel"],
            fg=COLORS["accent_blue"],
            cursor="hand2",
        )
        balance_link.pack(side=tk.RIGHT, padx=10, pady=8)
        balance_link.bind(
            "<Button-1>", lambda e: webbrowser.open("https://fal.ai/dashboard")
        )

        # DnD status
        dnd_status = "✓ Drag-Drop Enabled" if HAS_DND else "⚠ Drag-Drop Unavailable"
        dnd_color = COLORS["success"] if HAS_DND else COLORS["warning"]
        dnd_label = tk.Label(
            header,
            text=dnd_status,
            font=("Segoe UI", 8),
            bg=COLORS["bg_panel"],
            fg=dnd_color,
        )
        dnd_label.pack(side=tk.RIGHT, padx=10, pady=8)

    def _setup_queue_panel_content(self, queue_frame):
        """Set up the queue panel content inside the given frame."""
        # Header with count
        self.queue_header = tk.Label(
            queue_frame,
            text="📋 QUEUE (0/50)",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
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
            highlightthickness=0,
        )
        self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.queue_listbox.yview)

        # Context menu for queue
        self.queue_menu = tk.Menu(self.queue_listbox, tearoff=0)
        self.queue_menu.add_command(label="Remove", command=self._remove_selected_item)
        self.queue_listbox.bind("<Button-3>", self._show_queue_menu)

    def _setup_history_panel_content(self, panel):
        """Processed videos history content inside the given frame."""
        header = tk.Frame(panel, bg=COLORS["bg_panel"])
        header.pack(fill=tk.X, padx=5, pady=(4, 2))

        tk.Label(
            header,
            text="🎞️ PROCESSED VIDEOS",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_light"],
        ).pack(side=tk.LEFT)

        btn_frame = tk.Frame(header, bg=COLORS["bg_panel"])
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="Open File", command=self._open_selected_file).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(
            btn_frame, text="Open Folder", command=self._open_selected_folder
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_history_view).pack(
            side=tk.LEFT, padx=2
        )

        columns = ("time", "source", "output", "status")
        self.history_tree = ttk.Treeview(
            panel, columns=columns, show="headings", height=8, selectmode="browse"
        )
        for col, text, width in [
            ("time", "Time", 110),
            ("source", "Source", 180),
            ("output", "Output", 280),
            ("status", "Status", 90),
        ]:
            self.history_tree.heading(col, text=text)
            self.history_tree.column(col, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(
            panel, orient="vertical", command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=(0, 5)
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=(0, 5))

        self.history_tree.bind("<Double-1>", lambda e: self._open_selected_file())

        self._refresh_history_view()

    def _setup_controls(self):
        """Set up the control buttons."""
        control_frame = tk.Frame(self.root, bg=COLORS["bg_main"])
        # Use side=tk.BOTTOM to ensure buttons appear even with expandable main_frame
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

        # Left side: Add file button (fallback if DnD unavailable)
        if not HAS_DND:
            add_btn = tk.Button(
                control_frame,
                text="📁 Add...",
                font=("Segoe UI", 10),
                bg=COLORS["btn_green"],
                fg="white",
                command=self._browse_files,
            )
            add_btn.pack(side=tk.LEFT, padx=5)

        # Right side: Control buttons
        self.close_btn = tk.Button(
            control_frame,
            text="❌ Close",
            font=("Segoe UI", 10),
            bg=COLORS["btn_red"],
            fg="white",
            command=self._on_close,
        )
        self.close_btn.pack(side=tk.RIGHT, padx=5)

        self.clear_btn = tk.Button(
            control_frame,
            text="🗑️ Clear",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._clear_queue,
        )
        self.clear_btn.pack(side=tk.RIGHT, padx=5)

        self.retry_btn = tk.Button(
            control_frame,
            text="🔄 Retry Failed",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._retry_failed,
        )
        self.retry_btn.pack(side=tk.RIGHT, padx=5)

        self.pause_btn = tk.Button(
            control_frame,
            text="⏸️ Pause",
            font=("Segoe UI", 10),
            bg=COLORS["bg_input"],
            fg=COLORS["text_light"],
            command=self._toggle_pause,
        )
        self.pause_btn.pack(side=tk.RIGHT, padx=5)

    def _init_generator(self):
        """Initialize the video generator and queue manager."""
        if not HAS_GENERATOR:
            self._log(
                "Generator not available - check kling_generator_falai.py", "error"
            )
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
                model_display_name=self.config.get("model_display_name"),
                prompt_slot=self.config.get("current_prompt_slot", 1),
            )

            self.queue_manager = QueueManager(
                generator=self.generator,
                config_getter=lambda: self.config,
                log_callback=self._log_thread_safe,
                queue_update_callback=self._update_queue_display_thread_safe,
                processing_complete_callback=self._on_item_complete,
            )

            self._log("Generator initialized successfully", "success")

        except Exception as e:
            self._log(f"Failed to initialize generator: {e}", "error")

    def _log(self, message: str, level: str = "info"):
        """Log a message to the log display."""
        if hasattr(self, "log_display"):
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
                    "failed": "❌",
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
            tag = (
                "success"
                if status == "completed"
                else ("error" if status == "failed" else "")
            )
            self.history_tree.insert(
                "",
                tk.END,
                values=(
                    entry.get("time", ""),
                    os.path.basename(entry.get("source", "")),
                    entry.get("output", ""),
                    status,
                ),
                tags=(tag,),
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

    def _open_path_in_explorer(self, path: str):
        """Open a file or folder in the system's native file explorer.

        Uses platform-specific methods for reliable local file/folder opening.
        webbrowser.open() is unreliable for local paths on some systems.
        """
        import platform
        import subprocess

        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", path], check=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", path], check=True)
        except Exception as e:
            self._log(f"Could not open {path}: {e}", "error")

    def _open_selected_file(self):
        entry = self._get_selected_history()
        path = entry.get("output") if entry else None
        if path and os.path.exists(path):
            self._open_path_in_explorer(path)
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
                self._open_path_in_explorer(folder)
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
                self._log(
                    f"Skipped: {os.path.basename(file_path)} - {message}", "warning"
                )

        if added > 0:
            self._log(f"Added {added} file(s) to queue", "success")

    def _on_folder_dropped(self, folder_path: str):
        """Handle folder dropped onto the drop zone."""
        if not self.queue_manager:
            self._log("Queue manager not initialized", "error")
            return

        pattern = self.config.get("folder_filter_pattern", "").strip()
        match_mode = self.config.get("folder_match_mode", "partial")

        # Require pattern for folder processing - prompt if missing
        if not pattern:
            self._log("Folder dropped but no filter pattern set", "warning")
            pattern = simpledialog.askstring(
                "Pattern Required",
                "Enter a filename pattern to filter images (e.g. 'selfie'):",
                parent=self.root,
            )

            if not pattern:
                self._log("Folder processing cancelled: No pattern provided", "info")
                return

            # Update config and UI
            pattern = pattern.strip()
            self.config["folder_filter_pattern"] = pattern
            if hasattr(self, "config_panel"):
                self.config_panel.folder_pattern_var.set(pattern)
            self._save_config()

        # Scan for matching files
        self._log(f"Scanning folder: {os.path.basename(folder_path)}", "info")
        matches = self._scan_folder_for_images(folder_path, pattern, match_mode)

        if not matches:
            mode_text = "exactly matching" if match_mode == "exact" else "containing"
            self._log(f"No images found {mode_text} '{pattern}'", "warning")
            messagebox.showinfo(
                "No Matches",
                f"No images found {mode_text} '{pattern}' in:\n{folder_path}\n\n"
                f"Pattern mode: {match_mode}\n"
                f"Searched recursively through all subfolders.",
            )
            return

        # Show preview dialog
        self._show_folder_preview_dialog(matches, folder_path, pattern, match_mode)

    def _scan_folder_for_images(
        self, folder_path: str, pattern: str, match_mode: str
    ) -> List[str]:
        """
        Recursively scan folder for images matching pattern.

        Args:
            folder_path: Root folder to scan
            pattern: Filename pattern (case-insensitive)
            match_mode: "exact" or "partial"

        Returns:
            List of matching image file paths
        """
        matches = []
        pattern_lower = pattern.lower()

        try:
            for root, dirs, files in os.walk(folder_path):
                for filename in files:
                    name, ext = os.path.splitext(filename)
                    ext_lower = ext.lower()

                    # Check if valid image extension
                    if ext_lower not in VALID_EXTENSIONS:
                        continue

                    name_lower = name.lower()

                    # Apply matching logic
                    if match_mode == "exact":
                        if name_lower == pattern_lower:
                            matches.append(os.path.join(root, filename))
                    else:  # partial
                        if pattern_lower in name_lower:
                            matches.append(os.path.join(root, filename))
        except PermissionError as e:
            self._log(f"Permission denied accessing some folders: {e}", "warning")
        except Exception as e:
            self._log(f"Error scanning folder: {e}", "error")

        return sorted(matches)

    def _show_folder_preview_dialog(
        self, files: List[str], folder: str, pattern: str, match_mode: str
    ):
        """Show preview dialog and add files to queue if confirmed."""
        dialog = FolderPreviewDialog(self.root, files, folder, pattern, match_mode)

        if dialog.result:
            if self.queue_manager:
                # Add all files to queue
                added = 0
                skipped = 0
                for file_path in files:
                    success, msg = self.queue_manager.add_to_queue(file_path)
                    if success:
                        added += 1
                    else:
                        skipped += 1

                self._log(f"Added {added} images from folder to queue", "success")
                if skipped > 0:
                    self._log(
                        f"Skipped {skipped} (already in queue or duplicates)", "info"
                    )
            else:
                # Warn user that files weren't added
                self._log(
                    "Folder preview confirmed, but items were not added because the "
                    "queue/generator is not initialized yet.",
                    "warning",
                )

    def _on_config_changed(
        self, new_config: dict, change_description: Optional[str] = None
    ):
        """Handle configuration changes from the config panel."""
        self.config.update(new_config)
        self._save_config()

        # Update generator with new model if it exists and NOT currently processing
        # This prevents race conditions where settings change mid-generation
        if self.generator:
            if self.queue_manager and self.queue_manager.is_running:
                # Processing is active - don't update generator mid-run
                # Changes will apply to the next job (config is already saved)
                msg = (
                    f"{change_description} (will apply to next job)"
                    if change_description
                    else "Settings changed (will apply to next job)"
                )
                self._log(msg, "warning")
                return
            else:
                # Safe to update generator
                self.generator.update_model(
                    str(self.config.get("current_model", "")),
                    str(self.config.get("model_display_name", "")),
                )
                self.generator.update_prompt_slot(
                    int(self.config.get("current_prompt_slot", 1))
                )

        # Log the specific change if description provided
        if change_description:
            self._log(change_description, "info")

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
            self._log(
                f"Finished {os.path.basename(item.path)} → {item.output_path}",
                "success",
            )
        elif status == "failed":
            self._log(
                f"Failed {os.path.basename(item.path)}: {item.error_message}", "error"
            )

        # Sync generator with latest config when queue becomes empty
        # This ensures any settings changed during processing take effect for next run
        if self.queue_manager and not self.queue_manager.is_running and self.generator:
            self.generator.update_model(
                str(self.config.get("current_model", "")),
                str(self.config.get("model_display_name", "")),
            )
            self.generator.update_prompt_slot(
                int(self.config.get("current_prompt_slot", 1))
            )

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
        """Open chooser to add files or a folder (fallback for no DnD)."""
        choice = messagebox.askyesnocancel(
            "Add Items", "Add a folder?\n\nYes = Folder\nNo = Files"
        )
        if choice is None:
            return

        if choice:
            folder = filedialog.askdirectory(title="Select Folder to Process")
            if folder:
                self._on_folder_dropped(folder)
            return

        files = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tiff *.tif"),
                ("All files", "*.*"),
            ],
        )
        if files:
            self._on_files_dropped(list(files))

    def _restore_sash_positions(self):
        """Restore saved sash positions for all PanedWindows."""
        try:
            # Get saved positions from config (with new defaults)
            dropzone_pos = self.config.get("sash_dropzone", 180)
            queue_pos = self.config.get("sash_queue", 300)
            log_pos = self.config.get("sash_log", 380)

            # Restore main paned (drop zone height)
            if hasattr(self, "main_paned"):
                self.main_paned.sash_place(0, 0, dropzone_pos)

            # Restore bottom paned (queue width)
            if hasattr(self, "bottom_paned"):
                self.bottom_paned.sash_place(0, queue_pos, 0)

            # Restore right paned (log height)
            if hasattr(self, "right_paned"):
                self.right_paned.sash_place(0, 0, log_pos)

        except Exception as e:
            # Sash positions may fail on first run, that's OK
            pass

    def _save_layout(self):
        """Save window geometry and sash positions to config."""
        try:
            # Save window geometry (size and position)
            self.config["window_geometry"] = self.root.geometry()

            # Save sash positions
            if hasattr(self, "main_paned"):
                try:
                    sash_pos = self.main_paned.sash_coord(0)
                    if sash_pos:
                        self.config["sash_dropzone"] = sash_pos[
                            1
                        ]  # Y position for vertical paned
                except Exception:
                    pass

            if hasattr(self, "bottom_paned"):
                try:
                    sash_pos = self.bottom_paned.sash_coord(0)
                    if sash_pos:
                        self.config["sash_queue"] = sash_pos[
                            0
                        ]  # X position for horizontal paned
                except Exception:
                    pass

            if hasattr(self, "right_paned"):
                try:
                    sash_pos = self.right_paned.sash_coord(0)
                    if sash_pos:
                        self.config["sash_log"] = sash_pos[
                            1
                        ]  # Y position for vertical paned
                except Exception:
                    pass

        except Exception as e:
            pass  # Don't fail on layout save errors

    def _on_close(self):
        """Handle window close."""
        if self.queue_manager and self.queue_manager.is_running:
            if not messagebox.askyesno(
                "Confirm Close",
                "Processing is in progress. Are you sure you want to close?",
            ):
                return

            self.queue_manager.stop_processing()

        # Save layout (geometry + sash positions) before closing
        self._save_layout()
        self._save_history()
        self._save_config()

        # Clean up tkinter variables before destroying root to prevent
        # "main thread is not in main loop" errors on Python 3.14+
        if hasattr(self, "config_panel") and self.config_panel:
            self.config_panel.cleanup()

        # Process any pending events and quit mainloop before destroy
        # This ensures cleaner shutdown on Python 3.14+ with stricter thread safety
        try:
            self.root.update_idletasks()
            self.root.quit()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        """Run the GUI main loop."""
        self._log("GUI started - drag images to process", "info")
        self.root.mainloop()


def write_crash_log(error_type: str, error_msg: str, traceback_str: str):
    """Write crash information to a log file for debugging."""
    from datetime import datetime

    crash_log_path = get_crash_log_path()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    crash_info = f"""
{"=" * 60}
CRASH REPORT (GUI) - {timestamp}
{"=" * 60}
Error Type: {error_type}
Error Message: {error_msg}

Full Traceback:
{traceback_str}
{"=" * 60}

"""
    try:
        # Append to crash log (keep history)
        with open(crash_log_path, "a", encoding="utf-8") as f:
            f.write(crash_info)
        print(f"\n[Crash log saved to: {crash_log_path}]")
    except Exception as log_error:
        print(f"[Could not write crash log: {log_error}]")


def launch_gui(config_path: Optional[str] = None):
    """Launch the GUI window with crash handling."""
    import traceback

    try:
        window = KlingGUIWindow(config_path=config_path)

        window.run()
    except Exception as e:
        tb_str = traceback.format_exc()

        # Print full error to console
        print("\n" + "=" * 60)
        print("  FATAL ERROR - GUI Crashed")
        print("=" * 60)
        print(f"\nError: {type(e).__name__}: {e}")
        print("\nFull traceback:")
        print(tb_str)
        print("=" * 60)

        # Write to crash log file
        write_crash_log(type(e).__name__, str(e), tb_str)

        # Re-raise to ensure non-zero exit code
        raise


if __name__ == "__main__":
    try:
        launch_gui()
    except Exception:
        # Error already printed and logged by launch_gui
        import sys

        sys.exit(1)
