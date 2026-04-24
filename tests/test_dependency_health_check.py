import types
import unittest
from unittest import mock

import dependency_health_check as dhc


class DependencyHealthCheckTests(unittest.TestCase):
    def test_fails_for_broken_tensorflow_namespace(self):
        tf_module = types.SimpleNamespace()
        tf_keras_module = types.SimpleNamespace(__version__="2.16.0")
        retinaface_module = types.SimpleNamespace()
        cv2_module = types.SimpleNamespace()
        numpy_module = types.SimpleNamespace()

        modules = {
            "tensorflow": tf_module,
            "tf_keras": tf_keras_module,
            "retinaface": types.SimpleNamespace(RetinaFace=retinaface_module),
            "cv2": cv2_module,
            "numpy": numpy_module,
        }

        def fake_importer(name: str):
            if name == "tensorflow.compat.v2":
                raise ModuleNotFoundError("tensorflow.compat.v2")
            if name in modules:
                return modules[name]
            raise ModuleNotFoundError(name)

        ok, failures = dhc.check_runtime_dependencies(importer=fake_importer)
        self.assertFalse(ok)
        combined = "\n".join(failures)
        self.assertIn("tensorflow missing __version__", combined)
        self.assertIn("tensorflow.compat.v2 import failed", combined)

    def test_passes_for_valid_import_set(self):
        tf_module = types.SimpleNamespace(__version__="2.16.2")
        modules = {
            "tensorflow": tf_module,
            "tensorflow.compat.v2": types.SimpleNamespace(),
            "tf_keras": types.SimpleNamespace(__version__="2.16.0"),
            "retinaface": types.SimpleNamespace(RetinaFace=object()),
            "cv2": types.SimpleNamespace(),
            "numpy": types.SimpleNamespace(),
        }

        def fake_importer(name: str):
            if name in modules:
                return modules[name]
            raise ModuleNotFoundError(name)

        ok, failures = dhc.check_runtime_dependencies(importer=fake_importer)
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_verify_in_fresh_process_parses_failures(self):
        completed = types.SimpleNamespace(
            returncode=1,
            stdout="[dep-health] FAILED\n[dep-health] tensorflow missing __version__\n",
            stderr="",
        )
        with mock.patch("dependency_health_check.subprocess.run", return_value=completed):
            ok, failures = dhc.verify_in_fresh_process()

        self.assertFalse(ok)
        self.assertIn("tensorflow missing __version__", failures)

    def test_repair_mode_uses_fresh_process_verification(self):
        with mock.patch(
            "dependency_health_check.check_runtime_dependencies",
            return_value=(False, ["tensorflow missing __version__"]),
        ), mock.patch(
            "dependency_health_check.run_repair",
            return_value=(True, "repair install completed"),
        ), mock.patch(
            "dependency_health_check.verify_in_fresh_process",
            return_value=(True, []),
        ) as mock_verify:
            exit_code = dhc.main(["--mode", "repair"])

        self.assertEqual(exit_code, 0)
        mock_verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
