from __future__ import annotations

import io
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import main


class _DeepFaceStub:
    @staticmethod
    def build_model(model_name: str):
        return model_name

    @staticmethod
    def extract_faces(**kwargs):
        return [{"face": "face", "facial_area": {"w": 1, "h": 1}}]

    @staticmethod
    def represent(**kwargs):
        return [{"embedding": [1.0, 0.0, 0.0]}]


class TestMainRouting(unittest.TestCase):
    @staticmethod
    def _cli_dependency_modules(gui_module: types.ModuleType | None = None) -> dict[str, object]:
        deepface_module = types.ModuleType("deepface")
        deepface_module.DeepFace = _DeepFaceStub

        engine_module = types.ModuleType("src.engine")

        class _FaceEngineStub:
            def compare_images(self, *args, **kwargs):
                return {"match": True, "score": 100.0, "error": None}

            def extract_face(self, *args, **kwargs):
                return 0.99

            def initialize_models(self):
                return None

        engine_module.FaceEngine = _FaceEngineStub
        modules: dict[str, object] = {"deepface": deepface_module, "src.engine": engine_module}
        if gui_module is not None:
            modules["src.gui"] = gui_module
        return modules

    def test_similarity_mode_routes_to_batch_similarity(self) -> None:
        with patch.dict(sys.modules, self._cli_dependency_modules()):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)

            fake_instance = fake_cli.return_value

            with patch.object(sys, "argv", ["main.py", "--mode", "similarity", "--root", "C:/temp/root", "--yes"]):
                main.main()

        fake_instance.apply_runtime_config.assert_called_once()
        fake_instance.run_batch_similarity.assert_called_once_with(root_dir="C:/temp/root", confirm=False)

    def test_extract_mode_routes_to_batch_extraction(self) -> None:
        with patch.dict(sys.modules, self._cli_dependency_modules()):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)

            fake_instance = fake_cli.return_value

            with patch.object(sys, "argv", ["main.py", "--mode", "extract", "--root", "C:/temp/root", "--yes"]):
                main.main()

        fake_instance.apply_runtime_config.assert_called_once()
        fake_instance.run_batch_extraction.assert_called_once_with(root_dir="C:/temp/root", confirm=False)

    def test_compare_mode_routes_to_cli_run(self) -> None:
        with patch.dict(sys.modules, self._cli_dependency_modules()):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)

            fake_instance = fake_cli.return_value

            with patch.object(
                sys,
                "argv",
                ["main.py", "--mode", "compare", "--img1", "one.jpg", "--img2", "two.jpg"],
            ):
                main.main()

        fake_instance.apply_runtime_config.assert_called_once()
        fake_instance.run.assert_called_once_with(img1_path="one.jpg", img2_path="two.jpg")

    def test_cli_flag_only_launches_cli_instead_of_gui(self) -> None:
        gui_module = types.ModuleType("src.gui")
        gui_module.run_gui = MagicMock()

        with patch.dict(sys.modules, self._cli_dependency_modules(gui_module=gui_module)):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)

            with patch.object(sys, "argv", ["main.py", "--padding-ratio", "0.25"]):
                main.main()

        fake_cli.assert_called_once()
        fake_cli.return_value.apply_runtime_config.assert_called_once()
        fake_cli.return_value.run.assert_called_once_with()
        gui_module.run_gui.assert_not_called()

    def test_existing_file_mode_only_launches_cli_instead_of_gui(self) -> None:
        gui_module = types.ModuleType("src.gui")
        gui_module.run_gui = MagicMock()

        with patch.dict(sys.modules, self._cli_dependency_modules(gui_module=gui_module)):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)

            with patch.object(sys, "argv", ["main.py", "--existing-file-mode", "skip"]):
                main.main()

        fake_cli.assert_called_once()
        fake_cli.return_value.apply_runtime_config.assert_called_once()
        fake_cli.return_value.run.assert_called_once_with()
        gui_module.run_gui.assert_not_called()

    def test_no_cli_args_launches_gui(self) -> None:
        gui_module = types.ModuleType("src.gui")
        gui_module.run_gui = MagicMock()

        with patch.dict(sys.modules, self._cli_dependency_modules(gui_module=gui_module)):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)

            with patch.object(sys, "argv", ["main.py"]):
                main.main()

        gui_module.run_gui.assert_called_once_with()
        fake_cli.assert_not_called()

    def test_compare_mode_requires_both_paths(self) -> None:
        stdout = io.StringIO()

        with patch.dict(sys.modules, self._cli_dependency_modules()):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)

            with (
                patch.object(sys, "argv", ["main.py", "--mode", "compare", "--img1", "one.jpg"]),
                patch("sys.stdout", stdout),
            ):
                with self.assertRaises(SystemExit) as cm:
                    main.main()

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("requires both --img1 and --img2", stdout.getvalue())
        fake_cli.return_value.run.assert_not_called()

    def test_invalid_runtime_config_exits_with_usage_error(self) -> None:
        stderr = io.StringIO()

        with patch.dict(sys.modules, self._cli_dependency_modules()):
            fake_cli = patch("src.cli.ProCLI").start()
            self.addCleanup(patch.stopall)
            fake_cli.return_value.apply_runtime_config.side_effect = ValueError("bad padding")

            with (
                patch.object(sys, "argv", ["main.py", "--padding-ratio", "2"]),
                patch("sys.stderr", stderr),
            ):
                with self.assertRaises(SystemExit) as cm:
                    main.main()

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("Error: bad padding", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
