## 2026-02-28 - Distributable EXE Build

- **What changed:**
  - Created `create_icon.py` — Pillow-based icon generator producing `kling_ui.ico` (20 KB, 6 sizes: 16/32/48/64/128/256px). Design: dark navy background, blue gradient circle, white play triangle, "K" label.
  - Updated `kling_gui/main_window.py`: renamed title to "Kling UI - AI Video Generator", added `_set_app_icon()` method that loads `kling_ui.ico` from bundled resources or app directory.
  - Rewrote `kling_gui_direct.spec`: fixed tkinterdnd2 DLL inclusion via `collect_data_files`, added icon path, added `model_metadata`/`model_schema_manager` hidden imports, excludes bloat libs (matplotlib, numpy, PyQt).
  - Rewrote `build_gui_exe.bat`: robust 6-step build (verify Python → install deps → generate icon → clean → PyInstaller → ZIP). Creates `dist/KlingUI.zip` (23 MB) for easy sharing.
- **Why:** Codex previously failed to produce a working exe; needed proper icon, spec, and packaging.
- **Verified:** PyInstaller 6.19.0 build completed successfully. `dist/KlingUI/KlingUI.exe` (7.5 MB), `dist/KlingUI.zip` (23.3 MB) produced.
- **Key fix:** Pillow ICO save — must NOT use `sizes=` when using `append_images=`; they conflict and produce a 442-byte broken file.
