import builtins
import importlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock


class GuiStartupHotfixTests(unittest.TestCase):
    def test_ml_backend_env_sets_defaults_without_override(self):
        module = importlib.import_module("kling_gui.ml_backend_env")
        with mock.patch.dict(os.environ, {}, clear=True):
            module.ensure_ml_backend_env()
            self.assertEqual(os.environ.get("TF_USE_LEGACY_KERAS"), "1")
            self.assertEqual(os.environ.get("KERAS_BACKEND"), "tensorflow")

        with mock.patch.dict(
            os.environ,
            {"TF_USE_LEGACY_KERAS": "0", "KERAS_BACKEND": "jax"},
            clear=True,
        ):
            module.ensure_ml_backend_env()
            self.assertEqual(os.environ.get("TF_USE_LEGACY_KERAS"), "0")
            self.assertEqual(os.environ.get("KERAS_BACKEND"), "jax")

    def test_main_window_import_survives_retinaface_init_exception(self):
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "retinaface":
                raise AttributeError("module tensorflow has no attribute __version__")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            for module_name in [
                "kling_gui.main_window",
                "kling_gui.tabs",
                "kling_gui.tabs.face_crop_tab",
            ]:
                sys.modules.pop(module_name, None)

            module = importlib.import_module("kling_gui.main_window")
            self.assertTrue(hasattr(module, "KlingGUIWindow"))

    def test_face_crop_runtime_loader_catches_non_importerror(self):
        module = importlib.import_module("kling_gui.tabs.face_crop_tab")
        module._RETINAFACE_CLASS = None

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "retinaface":
                raise RuntimeError("tensorflow runtime broken")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch.object(module, "HAS_FACE_DEPS", True), \
            mock.patch.object(module, "FACE_DEPS_ERROR", ""), \
            mock.patch("builtins.__import__", side_effect=fake_import):
            retinaface_cls, retinaface_error = module._load_retinaface()

        self.assertIsNone(retinaface_cls)
        self.assertIn("RuntimeError", retinaface_error)

    def test_face_crop_loader_bootstraps_ml_env_before_import(self):
        module = importlib.import_module("kling_gui.tabs.face_crop_tab")
        module._RETINAFACE_CLASS = None

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "retinaface":
                raise RuntimeError("tensorflow runtime broken")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch.object(module, "HAS_FACE_DEPS", True), \
            mock.patch.object(module, "FACE_DEPS_ERROR", ""), \
            mock.patch.object(module, "ensure_ml_backend_env") as ensure_mock, \
            mock.patch("builtins.__import__", side_effect=fake_import):
            retinaface_cls, retinaface_error = module._load_retinaface()

        self.assertIsNone(retinaface_cls)
        self.assertIn("RuntimeError", retinaface_error)
        ensure_mock.assert_called_once_with()


class GuiLauncherBatchModeTests(unittest.TestCase):
    def test_batch_mode_import_failure_is_console_only(self):
        module = importlib.import_module("gui_launcher")

        with tempfile.TemporaryDirectory() as tmpdir:
            stderr_buffer = io.StringIO()
            with mock.patch.object(module, "CLI_ERROR_MODE", True), \
                mock.patch.object(module, "PATH_UTILS_AVAILABLE", False), \
                mock.patch.object(module, "_app_dir", tmpdir), \
                mock.patch.object(
                    module,
                    "_load_gui_window",
                    return_value=(None, "AttributeError: broken tensorflow", "traceback text"),
                ), \
                mock.patch.object(module, "show_critical_error") as mocked_popup, \
                mock.patch("sys.stderr", stderr_buffer):
                with self.assertRaises(SystemExit) as exit_ctx:
                    module.main()

            self.assertEqual(exit_ctx.exception.code, 1)
            mocked_popup.assert_not_called()

            stderr_text = stderr_buffer.getvalue()
            self.assertIn("Import Error:", stderr_text)
            self.assertIn("AttributeError: broken tensorflow", stderr_text)

            crash_log = os.path.join(tmpdir, "crash_log.txt")
            self.assertTrue(os.path.exists(crash_log))
            with open(crash_log, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Kling UI Initialization Failure", content)


if __name__ == "__main__":
    unittest.main()
