# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Kling UI
Build with: pyinstaller kling_ui.spec

SECURITY & RELIABILITY:
- No external .py bundled as data files (prevents code hijacking in one-folder builds)
- Uses collect_submodules for selenium/webdriver_manager to avoid missing imports
- UPX disabled to reduce AV false positives
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Get the distribution directory
dist_dir = Path(SPECPATH)

# Data files to include (NON-CODE files only)
datas = []

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # Path utilities
    'path_utils',

    # Tkinter and GUI
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinterdnd2',

    # Image processing
    'PIL',
    'PIL.Image',

    # Rich console
    'rich',
    'rich.console',
    'rich.progress',
    'rich.panel',
    'rich.text',
    'rich.table',
    'rich.live',
    'rich.spinner',

    # Requests
    'requests',

    # Standard library
    'json',
    'logging',
    'threading',
    'concurrent.futures',
    'urllib.request',
    'urllib.parse',
    'base64',
    'hashlib',

    # Kling modules
    'kling_generator_falai',
    'balance_tracker',
    'selenium_balance_checker',
    'dependency_checker',

    # Kling GUI modules (explicit)
    'kling_gui',
    'kling_gui.main_window',
    'kling_gui.config_panel',
    'kling_gui.drop_zone',
    'kling_gui.log_display',
    'kling_gui.queue_manager',
    'kling_gui.video_looper',
]

# Selenium: Collect ALL selenium modules to avoid runtime import failures
hiddenimports.extend(collect_submodules('selenium'))

# WebDriver Manager: Collect all submodules
hiddenimports.extend(collect_submodules('webdriver_manager'))

a = Analysis(
    [str(dist_dir / 'kling_automation_ui.py')],
    pathex=[str(dist_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(dist_dir / 'hooks')],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Try to add tkinterdnd2 DLLs and TCL files
try:
    import tkinterdnd2
    tkdnd_path = Path(tkinterdnd2.__file__).parent

    # Find and add tkdnd DLLs
    for dll_file in tkdnd_path.glob('**/*.dll'):
        rel_path = dll_file.relative_to(tkdnd_path).parent
        a.datas.append((str(dll_file), str(Path('tkinterdnd2') / rel_path), 'DATA'))

    for tcl_file in tkdnd_path.glob('**/*.tcl'):
        rel_path = tcl_file.relative_to(tkdnd_path).parent
        a.datas.append((str(tcl_file), str(Path('tkinterdnd2') / rel_path), 'DATA'))
except ImportError:
    print("Warning: tkinterdnd2 not found, drag-drop may not work in built exe")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KlingUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Keep console for error visibility
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='KlingUI',
)
