"""
Kling UI - Direct GUI Launcher
Entry point for PyInstaller to create a GUI-only executable.
Bypasses the CLI menu and launches the Tkinter GUI directly.

SECURITY: Only loads modules from the bundled _MEIPASS directory.
External .py files next to the exe are NOT imported (prevents code hijacking).
"""

import sys
import os
import traceback
from pathlib import Path

# Add appropriate directories to path for imports
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    # _MEIPASS is where PyInstaller extracts bundled files (internal)
    _bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    _app_dir = os.path.dirname(sys.executable)
    
    # SECURITY: Only use the bundled directory, NOT external files
    # This prevents code hijacking if .py files are placed next to the exe
    if _bundle_dir not in sys.path:
        sys.path.insert(0, _bundle_dir)
    # NOTE: _app_dir is NOT added to sys.path for security
    # All modules must be bundled via PyInstaller
else:
    # Running as script - app dir is where gui_launcher.py is
    _app_dir = os.path.dirname(os.path.abspath(__file__))
    if _app_dir not in sys.path:
        sys.path.insert(0, _app_dir)

# Import path utilities for frozen exe compatibility
try:
    from path_utils import get_app_dir, get_crash_log_path
    PATH_UTILS_AVAILABLE = True
except Exception:
    PATH_UTILS_AVAILABLE = False

CLI_ERROR_MODE = os.getenv("KLING_GUI_CLI_ERRORS", "").strip() == "1"


def _load_gui_window():
    """Import GUI entry lazily so module import is testable and robust."""
    try:
        from kling_gui.main_window import KlingGUIWindow

        return KlingGUIWindow, "", ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", traceback.format_exc()


def show_critical_error(title, message):
    """Fallback error reporting using tkinter, with silent fail if tkinter missing."""
    if CLI_ERROR_MODE:
        sys.stderr.write(f"{title}: {message}\n")
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        # If tkinter is also broken, we have no choice but to print (if console exists)
        # In GUI-only mode (console=False), this might not be seen unless redirected.
        sys.stderr.write(f"CRITICAL ERROR: {title}\n{message}\n")


def main():
    """Launch the Tkinter GUI directly."""
    KlingGUIWindow, import_error, import_traceback = _load_gui_window()
    if KlingGUIWindow is None:
        # Fallback error handling if GUI can't be imported
        error_msg = (
            f"Failed to initialize Kling GUI:\n\n{import_error}\n\n"
            f"Please ensure all dependencies are installed:\n"
            f"pip install requests pillow rich tkinterdnd2 selenium webdriver-manager "
            f"opencv-python-headless numpy tensorflow==2.16.2 "
            f"tensorflow-intel==2.16.2 tf-keras==2.16.0 retina-face==0.0.17 deepface==0.0.92\n\n"
            f"If you're running the standalone exe, this may indicate a build issue.\n"
            f"All dependencies should be bundled internally."
        )
        
        # Log crash to file if possible
        crash_log = "crash_log.txt"
        if PATH_UTILS_AVAILABLE:
            try:
                crash_log = get_crash_log_path()
            except Exception:
                pass
        
        if not os.path.isabs(crash_log):
            crash_log = os.path.join(_app_dir, crash_log)

        try:
            with open(crash_log, 'w', encoding='utf-8') as f:
                f.write("Kling UI Initialization Failure\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Error: {import_error}\n\n")
                f.write("Traceback:\n")
                f.write(import_traceback)
            error_msg += f"\n\nDetails saved to:\n{crash_log}"
        except Exception:
            pass
        if CLI_ERROR_MODE:
            sys.stderr.write(f"Import Error: {error_msg}\n")
        else:
            show_critical_error("Import Error", error_msg)
        sys.exit(1)
    
    try:
        # Create and run the GUI window
        app = KlingGUIWindow()
        app.run()
    except Exception as e:
        # Log crash to file for debugging
        crash_log = "crash_log.txt"
        if PATH_UTILS_AVAILABLE:
            try:
                crash_log = get_crash_log_path()
            except Exception:
                pass
        
        if not os.path.isabs(crash_log):
            crash_log = os.path.join(_app_dir, crash_log)
        
        try:
            with open(crash_log, 'w', encoding='utf-8') as f:
                f.write("Kling UI Runtime Crash Report\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Error: {str(e)}\n\n")
                f.write("Traceback:\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        
        runtime_msg = (
            f"An unexpected error occurred:\n\n{str(e)}\n\n"
            f"Crash log saved to:\n{crash_log}"
        )
        if CLI_ERROR_MODE:
            sys.stderr.write(f"Kling UI Error: {runtime_msg}\n")
        else:
            show_critical_error("Kling UI Error", runtime_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
