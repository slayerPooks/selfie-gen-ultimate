from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


class TestLauncherScripts(unittest.TestCase):
    def test_windows_launchers_sync_dependencies_after_existing_venv_activation(self) -> None:
        for script in ("run_gui.bat", "run_cli.bat"):
            with self.subTest(script=script):
                text = _read(script)
                existing_idx = text.index("echo [INFO] Activating existing virtual environment...")
                sync_idx = text.index("python -m pip install -r requirements.txt")
                self.assertGreater(sync_idx, existing_idx)

    def test_command_launchers_sync_dependencies_after_existing_venv_activation(self) -> None:
        for script in ("run_gui.command", "run_cli.command"):
            with self.subTest(script=script):
                text = _read(script)
                existing_idx = text.index('echo "[INFO] Activating existing virtual environment..."')
                sync_idx = text.index("python -m pip install -r requirements.txt")
                self.assertGreater(sync_idx, existing_idx)

    def test_all_launchers_fail_fast_when_dependency_sync_fails(self) -> None:
        expectations = {
            "run_gui.bat": [
                "if errorlevel 1 (",
                "echo [ERROR] Failed to synchronize dependencies from requirements.txt.",
                "exit /b 1",
            ],
            "run_cli.bat": [
                "if errorlevel 1 (",
                "echo [ERROR] Failed to synchronize dependencies from requirements.txt.",
                "exit /b 1",
            ],
            "run_gui.command": [
                "if [ $? -ne 0 ]; then",
                'echo "[ERROR] Failed to synchronize dependencies from requirements.txt."',
                "exit 1",
            ],
            "run_cli.command": [
                "if [ $? -ne 0 ]; then",
                'echo "[ERROR] Failed to synchronize dependencies from requirements.txt."',
                "exit 1",
            ],
        }

        for script, needles in expectations.items():
            with self.subTest(script=script):
                text = _read(script)
                for needle in needles:
                    self.assertIn(needle, text)

    def test_gui_launchers_require_tkinter_capability(self) -> None:
        command_text = _read("run_gui.command")
        self.assertIn('import tkinter', command_text)
        self.assertIn("lacks Tk support", command_text)

        windows_text = _read("run_gui.bat")
        self.assertIn("import sys, tkinter", windows_text)
        self.assertIn("lacks Tk support", windows_text)

    def test_cli_launchers_only_require_supported_python_version(self) -> None:
        command_text = _read("run_cli.command")
        self.assertNotIn("import tkinter", command_text)
        self.assertIn("requires 3.9-3.12", command_text)

        windows_text = _read("run_cli.bat")
        self.assertNotIn("import sys, tkinter", windows_text)
        self.assertIn("requires 3.9-3.12", windows_text)


if __name__ == "__main__":
    unittest.main()
