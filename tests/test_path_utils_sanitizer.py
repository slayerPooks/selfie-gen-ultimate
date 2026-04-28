import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from path_utils import (
    sanitize_filename,
    sanitize_stem,
    make_unique_name,
    sanitize_path_name,
    sanitize_tree_names,
    sanitize_tree_names_report,
)


class PathSanitizerTests(unittest.TestCase):
    @contextmanager
    def _workspace(self):
        root = os.path.join(os.getcwd(), "tests_tmp", f"pathfix-{uuid.uuid4().hex}")
        os.makedirs(root, exist_ok=True)
        try:
            yield root
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_sanitize_filename_removes_illegal_and_controls(self):
        value = sanitize_filename('bad<>:"/\\|?*\nname .txt')
        self.assertEqual(value, "bad_name.txt")

    def test_sanitize_stem_protects_windows_reserved_names(self):
        self.assertEqual(sanitize_stem("con"), "con_file")
        self.assertEqual(sanitize_stem("LPT1"), "LPT1_file")

    def test_make_unique_name_appends_numeric_suffix(self):
        with self._workspace() as root:
            target = os.path.join(root, "sample.txt")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("x")
            candidate = make_unique_name(root, "sample.txt")
            self.assertEqual(candidate, "sample_2.txt")

    def test_sanitize_path_name_renames_file_without_overwrite(self):
        with self._workspace() as root:
            first = os.path.join(root, "bad__name.txt")
            second = os.path.join(root, "bad_name.txt")
            with open(first, "w", encoding="utf-8") as handle:
                handle.write("a")
            with open(second, "w", encoding="utf-8") as handle:
                handle.write("b")

            new_path, changed = sanitize_path_name(first)
            self.assertTrue(changed)
            self.assertTrue(new_path.endswith("bad_name_2.txt"))
            self.assertTrue(os.path.isfile(new_path))
            self.assertTrue(os.path.isfile(second))

    def test_sanitize_tree_names_recursive(self):
        with self._workspace() as root:
            nested_bad_dir = os.path.join(root, "bad__folder")
            os.makedirs(nested_bad_dir, exist_ok=True)
            bad_file = os.path.join(nested_bad_dir, "line__break.png")
            with open(bad_file, "w", encoding="utf-8") as handle:
                handle.write("data")

            new_root, renames = sanitize_tree_names(root, rename_root=False)
            self.assertEqual(new_root, root)
            self.assertGreaterEqual(len(renames), 2)

            expected_dir = os.path.join(root, "bad_folder")
            expected_file = os.path.join(expected_dir, "line_break.png")
            self.assertTrue(os.path.isdir(expected_dir))
            self.assertTrue(os.path.isfile(expected_file))

    def test_sanitize_tree_names_report_continues_on_rename_error(self):
        with self._workspace() as root:
            blocked_name = os.path.join(root, "LOCKED__bad.txt")
            ok_name = os.path.join(root, "good__name.txt")
            with open(blocked_name, "w", encoding="utf-8") as handle:
                handle.write("x")
            with open(ok_name, "w", encoding="utf-8") as handle:
                handle.write("y")

            original_rename = os.rename

            def flaky_rename(src, dst):
                if src.endswith("LOCKED__bad.txt"):
                    raise PermissionError(5, "Access is denied", src)
                return original_rename(src, dst)

            with patch("path_utils.os.rename", side_effect=flaky_rename):
                new_root, renames, failures, changes = sanitize_tree_names_report(
                    root, rename_root=False
                )

            self.assertEqual(new_root, root)
            self.assertEqual(len(renames), 1)
            self.assertTrue(renames[0][0].endswith("good__name.txt"))
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0]["reason"], "repeated_underscores")
            self.assertEqual(len(failures), 1)
            self.assertTrue(failures[0]["path"].endswith("LOCKED__bad.txt"))
            self.assertIn("error_type", failures[0])
            self.assertIn("error_message", failures[0])
            self.assertTrue(os.path.exists(blocked_name))
            self.assertTrue(os.path.exists(renames[0][1]))

    def test_sanitize_tree_names_report_keeps_normal_dash_spacing(self):
        with self._workspace() as root:
            current_name = "DASHER - Emily Kramer (397077)_front"
            original_folder = os.path.join(root, current_name)
            os.makedirs(original_folder, exist_ok=True)

            new_root, renames, failures, changes = sanitize_tree_names_report(
                original_folder, rename_root=True
            )

            self.assertEqual(new_root, original_folder)
            self.assertEqual(renames, [])
            self.assertEqual(failures, [])
            self.assertEqual(changes, [])

    def test_sanitize_tree_names_legacy_wrapper_compat(self):
        with self._workspace() as root:
            bad_name = os.path.join(root, "legacy__name.txt")
            with open(bad_name, "w", encoding="utf-8") as handle:
                handle.write("legacy")

            new_root, renames = sanitize_tree_names(root, rename_root=False)
            self.assertEqual(new_root, root)
            self.assertEqual(len(renames), 1)
            self.assertTrue(renames[0][1].endswith("legacy_name.txt"))


if __name__ == "__main__":
    unittest.main()
