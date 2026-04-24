import os
import tempfile
import unittest

from kling_gui.image_state import ImageEntry, ImageSession
from kling_gui.tabs.expand_tab import ExpandTab


class CanonicalSimilarityReferenceTests(unittest.TestCase):
    def _touch(self, folder: str, name: str) -> str:
        path = os.path.join(folder, name)
        with open(path, "wb") as handle:
            handle.write(b"x")
        return path

    def test_prefers_crop_then_front_then_reference_then_first_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plain = self._touch(tmpdir, "plain_input.png")
            front = self._touch(tmpdir, "front_image.png")
            crop = self._touch(tmpdir, "subject_crop.jpg")
            selfie = self._touch(tmpdir, "selfie_sim80_001.png")

            session = ImageSession()
            session.add_image(plain, "input")
            session.add_image(front, "input")
            session.add_image(crop, "input")
            session.add_image(selfie, "selfie")

            self.assertEqual(session.canonical_similarity_ref_entry.path, crop)

            os.remove(crop)
            self.assertEqual(session.canonical_similarity_ref_entry.path, front)

            os.remove(front)
            self.assertEqual(session.canonical_similarity_ref_entry.path, plain)

    def test_falls_back_to_first_existing_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = self._touch(tmpdir, "a.png")
            second = self._touch(tmpdir, "b.png")
            session = ImageSession()
            session.add_image(first, "input")
            session.add_image(second, "input")
            # Current session behavior sets reference_index to latest input.
            self.assertEqual(session.canonical_similarity_ref_entry.path, second)
            # If stored reference is invalid, resolver falls back to first input.
            session._reference_index = -1
            self.assertEqual(session.canonical_similarity_ref_entry.path, first)


class Expand25CandidateCompositionTests(unittest.TestCase):
    def _entry(self, folder: str, name: str, source_type: str):
        path = os.path.join(folder, name)
        with open(path, "wb") as handle:
            handle.write(b"x")
        return ImageEntry(path=path, source_type=source_type)

    def test_includes_active_non_selfie_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            selfie = self._entry(tmpdir, "selfie_sim81_001.png", "selfie")
            active_input = self._entry(tmpdir, "front_crop.jpg", "input")
            entries = ExpandTab.compose_candidate_entries([selfie], active_input)
            self.assertEqual([e.path for e in entries], [selfie.path, active_input.path])

    def test_dedupes_when_active_already_in_selfie_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            selfie = self._entry(tmpdir, "selfie_sim85_001.png", "selfie")
            entries = ExpandTab.compose_candidate_entries([selfie], selfie)
            self.assertEqual([e.path for e in entries], [selfie.path])


if __name__ == "__main__":
    unittest.main()
