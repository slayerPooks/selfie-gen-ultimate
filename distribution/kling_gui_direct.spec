# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Kling UI - Direct GUI Launcher
Build with: pyinstaller kling_gui_direct.spec
Creates a standalone executable that launches the Tkinter GUI directly (no CLI menu)

SECURITY & RELIABILITY IMPROVEMENTS:
- Uses collect_submodules for Selenium to avoid missing imports
- UPX disabled to prevent AV false positives
- No redundant external .py file bundling (security risk)
- All code bundled internally via PyInstaller
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Get the distribution directory
dist_dir = Path(SPECPATH)

# Data files to include (NON-CODE files only)
# NOTE: Python modules are bundled via Analysis, not as data files
datas = [
    # NOTE: kling_gui package is auto-discovered by Analysis
    # NOTE: .py files are NOT bundled as data - they're compiled into the exe
    # Only include non-code resources here if needed
]

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
    
    # Rich console (for generator)
    'rich',
    'rich.console',
    'rich.progress',
    'rich.panel',
    'rich.text',
    'rich.table',
    'rich.live',
    'rich.spinner',
    
    # Standard library
    'json',
    'logging',
    'threading',
    'concurrent.futures',
    'urllib.request',
    'urllib.parse',
    'base64',
    'hashlib',
    
    # Requests
    'requests',
    
    # Kling GUI modules (explicit)
    'kling_gui',
    'kling_gui.main_window',
    'kling_gui.config_panel',
    'kling_gui.drop_zone',
    'kling_gui.log_display',
    'kling_gui.queue_manager',
    'kling_gui.video_looper',
    
    # Generator and checkers
    'kling_generator_falai',
    'balance_tracker',
    'selenium_balance_checker',
    'dependency_checker',
]

# Selenium: Use collect_submodules to get ALL selenium modules
# This prevents runtime import failures for selenium.webdriver.* submodules
selenium_imports = collect_submodules('selenium')
hiddenimports.extend(selenium_imports)

# WebDriver Manager: Collect all submodules
webdriver_manager_imports = collect_submodules('webdriver_manager')
hiddenimports.extend(webdriver_manager_imports)

a = Analysis(
    [str(dist_dir / 'gui_launcher.py')],  # Direct GUI entry point
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
    name='KlingGUI_Direct',  # Distinct name from CLI version
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # DISABLED: UPX causes AV false positives and can break runtime
    console=False,  # No console window for GUI-only version
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
    upx=False,  # DISABLED: Consistent with EXE setting
    upx_exclude=[],
    name='KlingGUI_Direct',
)
