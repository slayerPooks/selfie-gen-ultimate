import json
import os
import shutil
import unittest
import uuid
from contextlib import contextmanager

from kling_gui import session_manager as sm


class _DummyEntry:
    def __init__(self, path: str):
        self.path = path


class _DummySession:
    def __init__(self, source_path: str):
        self.reference_entry = _DummyEntry(source_path)
        self.input_images = [(0, _DummyEntry(source_path))]
        self.images = [_DummyEntry(source_path)]
        self.count = 1

    def to_dict(self) -> dict:
        return {
            "images": [{"path": self.reference_entry.path, "source_type": "input"}],
            "current_index": 0,
            "reference_index": 0,
            "similarity_ref_index": -1,
        }


class SessionManagerTests(unittest.TestCase):
    @contextmanager
    def _workspace(self):
        root = os.path.join(os.getcwd(), "tests_tmp", f"sessions-{uuid.uuid4().hex}")
        os.makedirs(root, exist_ok=True)
        try:
            yield root
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def _make_session(self, root: str, project_name: str) -> _DummySession:
        project_dir = os.path.join(root, project_name)
        os.makedirs(project_dir, exist_ok=True)
        source_path = os.path.join(project_dir, f"{project_name}_front.png")
        with open(source_path, "wb") as handle:
            handle.write(b"x")
        return _DummySession(source_path)

    def test_legacy_file_lists_with_inferred_metadata(self):
        with self._workspace() as app_dir:
            sessions_dir = os.path.join(app_dir, "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            legacy_path = os.path.join(sessions_dir, "alpha_autosave.json")
            payload = {
                "name": "alpha_autosave",
                "session": {"images": [{"path": "x.png"}]},
            }
            with open(legacy_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            listed = sm.list_sessions(app_dir)
            self.assertEqual(len(listed), 1)
            rec = listed[0]
            self.assertEqual(rec.session_kind, sm.SESSION_KIND_AUTOSAVE)
            self.assertEqual(rec.project_key, "alpha")
            self.assertEqual(rec.image_count, 1)
            self.assertTrue(rec.updated_at)

    def test_autosaves_are_versioned_and_pruned(self):
        with self._workspace() as app_dir:
            session = self._make_session(app_dir, "project_one")
            for _ in range(12):
                sm.save_session(
                    app_dir,
                    session,
                    config={},
                    session_kind=sm.SESSION_KIND_AUTOSAVE,
                    autosave_retention=10,
                )

            listed = sm.list_sessions(app_dir)
            autosaves = [
                rec for rec in listed
                if rec.session_kind == sm.SESSION_KIND_AUTOSAVE and rec.project_key == "project_one"
            ]
            self.assertEqual(len(autosaves), 10)
            names = {os.path.basename(rec.path) for rec in autosaves}
            self.assertEqual(len(names), 10)

    def test_manual_saves_are_not_pruned_by_autosave_retention(self):
        with self._workspace() as app_dir:
            session = self._make_session(app_dir, "project_two")
            manual_path = sm.save_session(
                app_dir,
                session,
                config={},
                name="project_two_manual",
                session_kind=sm.SESSION_KIND_MANUAL,
            )
            for _ in range(11):
                sm.save_session(
                    app_dir,
                    session,
                    config={},
                    session_kind=sm.SESSION_KIND_AUTOSAVE,
                    autosave_retention=10,
                )

            self.assertTrue(os.path.isfile(manual_path))
            listed = sm.list_sessions(app_dir)
            manual = [rec for rec in listed if rec.session_kind == sm.SESSION_KIND_MANUAL]
            autosave = [rec for rec in listed if rec.session_kind == sm.SESSION_KIND_AUTOSAVE]
            self.assertEqual(len(manual), 1)
            self.assertEqual(len(autosave), 10)

    def test_delete_project_sessions_removes_only_target_project(self):
        with self._workspace() as app_dir:
            session_a = self._make_session(app_dir, "alpha")
            session_b = self._make_session(app_dir, "bravo")

            sm.save_session(app_dir, session_a, {}, session_kind=sm.SESSION_KIND_AUTOSAVE)
            sm.save_session(app_dir, session_a, {}, name="alpha_manual", session_kind=sm.SESSION_KIND_MANUAL)
            sm.save_session(app_dir, session_b, {}, name="bravo_manual", session_kind=sm.SESSION_KIND_MANUAL)

            removed = sm.delete_project_sessions(app_dir, "alpha")
            self.assertGreaterEqual(removed, 2)
            remaining = sm.list_sessions(app_dir)
            remaining_projects = {rec.project_key for rec in remaining}
            self.assertEqual(remaining_projects, {"bravo"})

    def test_sort_uses_updated_at_then_timestamp_then_mtime(self):
        with self._workspace() as app_dir:
            sessions_dir = os.path.join(app_dir, "sessions")
            os.makedirs(sessions_dir, exist_ok=True)

            older_path = os.path.join(sessions_dir, "older_manual.json")
            newer_path = os.path.join(sessions_dir, "newer_manual.json")
            with open(older_path, "w", encoding="utf-8") as handle:
                json.dump({"name": "older", "session_kind": "manual", "session": {"images": []}}, handle)
            with open(newer_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "name": "newer",
                        "session_kind": "manual",
                        "updated_at": "2099-01-01T00:00:00",
                        "session": {"images": []},
                    },
                    handle,
                )
            os.utime(older_path, (1_600_000_000, 1_600_000_000))
            os.utime(newer_path, (1_500_000_000, 1_500_000_000))

            listed = sm.list_sessions(app_dir)
            self.assertEqual(listed[0].name, "newer")
            self.assertEqual(listed[1].name, "older")


if __name__ == "__main__":
    unittest.main()
