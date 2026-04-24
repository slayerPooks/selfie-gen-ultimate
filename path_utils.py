"""
Path utilities for PyInstaller compatibility.
Provides functions to get correct paths whether running as script or frozen exe.
"""

import os
import sys


APP_NAME = "selfie-gen-ultimate"

# Valid image extensions for processing
VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tiff', '.tif'}


def get_app_dir() -> str:
    """
    Get the directory where the application is located.
    
    When running as a script: Returns the directory containing the main .py file
    When running as frozen exe: Returns the directory containing the .exe
    
    Returns:
        str: Absolute path to the application directory
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        # sys.executable points to the .exe file
        return os.path.dirname(sys.executable)
    else:
        # Running as a Python script
        # Use the directory of the main module
        return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_resource_dir() -> str:
    """
    Get the directory where bundled resources are located.
    
    When running as a script: Same as get_app_dir()
    When running as frozen exe: Returns the _MEIPASS temp directory
    
    This is for read-only bundled resources, not user data.
    
    Returns:
        str: Absolute path to the resource directory
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        # _MEIPASS contains extracted bundled files
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # Running as a Python script
        return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_config_path(filename: str = "kling_config.json") -> str:
    """
    Get the full path for a configuration file.
    On macOS, config files are stored in Application Support. On Windows,
    keep the app-local path to preserve the tested portable workflow.
    
    Args:
        filename: Name of the config file
        
    Returns:
        str: Full path to the config file
    """
    base_dir = get_user_data_dir() if sys.platform == "darwin" else get_app_dir()
    return os.path.join(base_dir, filename)


def get_log_path(filename: str = "kling_gui.log") -> str:
    """
    Get the full path for a log file.
    On macOS, log files are stored in Application Support. On Windows,
    keep the app-local path to preserve the tested portable workflow.
    
    Args:
        filename: Name of the log file
        
    Returns:
        str: Full path to the log file
    """
    base_dir = get_user_data_dir() if sys.platform == "darwin" else get_app_dir()
    return os.path.join(base_dir, filename)


def get_crash_log_path() -> str:
    """
    Get the full path for the crash log file.
    
    Returns:
        str: Full path to crash_log.txt
    """
    base_dir = get_user_data_dir() if sys.platform == "darwin" else get_app_dir()
    return os.path.join(base_dir, "crash_log.txt")


def get_user_data_dir(app_name: str = APP_NAME) -> str:
    """
    Get the directory for storing user data such as config, logs, caches, and sessions.

    Platform conventions:
    - macOS: ~/Library/Application Support/<app_name>
    - Windows: %APPDATA%/<app_name>
    - Linux: ~/.local/share/<app_name>
    """
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

    path = os.path.join(base, app_name)
    try:
        if os.path.exists(path) and not os.path.isdir(path):
            return get_app_dir()
        os.makedirs(path, exist_ok=True)
    except OSError:
        return get_app_dir()
    return path


def is_frozen() -> bool:
    """
    Check if running as a frozen executable.

    Returns:
        bool: True if running as exe, False if running as script
    """
    return getattr(sys, 'frozen', False)


_GEN_FOLDER_NAMES = {"gen-images", "gen-videos"}


def _walk_up_past_gen_folders(source_path: str) -> str:
    """Walk up from *source_path*'s parent dir past any gen-images/gen-videos nesting."""
    current = os.path.dirname(os.path.abspath(source_path))
    while os.path.basename(current) in _GEN_FOLDER_NAMES:
        current = os.path.dirname(current)
    return current


def get_gen_images_folder(source_path: str) -> str:
    """Return the gen-images subfolder path next to the given source file.

    Walks up past any existing gen-images/gen-videos directories to prevent
    nesting when piping output through multiple tabs.

    Pure path computation — does NOT call os.makedirs.
    Each caller is responsible for creating it before writing.
    """
    return os.path.join(_walk_up_past_gen_folders(source_path), "gen-images")


def get_gen_videos_folder(source_path: str) -> str:
    """Return the gen-videos subfolder path next to the given source file.

    Same anti-nesting logic as get_gen_images_folder() but for video output.

    Pure path computation — does NOT call os.makedirs.
    Each caller is responsible for creating it before writing.
    """
    return os.path.join(_walk_up_past_gen_folders(source_path), "gen-videos")
