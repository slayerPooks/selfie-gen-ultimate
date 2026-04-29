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

    def test_gui_cli_launcher_setup_blocks_match_per_platform(self) -> None:
        windows_setup_gui = self._extract_setup_block(_read("run_gui.bat"), ":: Check if .venv exists", ":: Run the application")
        windows_setup_cli = self._extract_setup_block(_read("run_cli.bat"), ":: Check if .venv exists", ":: Run the application")
        self.assertEqual(windows_setup_gui, windows_setup_cli)

        command_setup_gui = self._extract_setup_block(_read("run_gui.command"), "# Check if .venv exists", "# Run the application")
        command_setup_cli = self._extract_setup_block(_read("run_cli.command"), "# Check if .venv exists", "# Run the application")
        self.assertEqual(command_setup_gui, command_setup_cli)

    @staticmethod
    def _extract_setup_block(text: str, start_marker: str, end_marker: str) -> str:
        start = text.index(start_marker)
        end = text.index(end_marker)
        return text[start:end].strip()


if __name__ == "__main__":
    unittest.main()
