import os
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest import mock

from kling_gui.carousel_widget import ImageCarousel
from kling_gui.image_state import ImageSession


class _FakeButton:
    def __init__(self):
        self.calls = []

    def config(self, **kwargs):
        self.calls.append(kwargs)


class _FakeCanvas:
    def delete(self, *_args, **_kwargs):
        return None

    def winfo_width(self):
        return 400

    def winfo_height(self):
        return 300

    def create_text(self, *_args, **_kwargs):
        return None


class CarouselRefControlsTests(unittest.TestCase):
    def test_ref_and_compare_have_stable_widths(self):
        root = tk.Tk()
        root.withdraw()
        try:
            session = ImageSession()
            widget = ImageCarousel(root, session, lambda *_args: None)
            self.assertEqual(int(widget._ref_btn.cget("width")), 10)
            self.assertEqual(int(widget.compare_btn.cget("width")), 10)
        finally:
            root.destroy()

    def test_ref_button_lights_when_active_image_is_effective_ref(self):
        tab = ImageCarousel.__new__(ImageCarousel)
        tab.canvas = _FakeCanvas()
        tab.remove_btn = _FakeButton()
        tab.compare_btn = _FakeButton()
        tab.prev_btn = _FakeButton()
        tab.next_btn = _FakeButton()
        tab._ref_btn = _FakeButton()
        tab.counter_label = _FakeButton()
        tab.info_label = _FakeButton()
        tab.meta_label = _FakeButton()
        tab.sim_label = _FakeButton()
        tab._show_image_on_canvas = lambda *_args, **_kwargs: None

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "front.png")
            with open(image_path, "wb") as handle:
                handle.write(b"x")
            session = ImageSession()
            session.add_image(image_path, "input", make_active=True)
            tab.image_session = session
            tab._update_panel()

        has_clear = any(call.get("text") == "★ Clear" for call in tab._ref_btn.calls)
        has_active_color = any(call.get("bg") == "#E5C100" for call in tab._ref_btn.calls)
        self.assertTrue(has_clear)
        self.assertTrue(has_active_color)

    def test_toggle_ref_sets_and_clears_manual_ref(self):
        tab = ImageCarousel.__new__(ImageCarousel)
        tab.log = mock.Mock()
        tab._calc_all_similarity = mock.Mock()
        session = ImageSession()
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.png")
            p2 = os.path.join(tmpdir, "b.png")
            open(p1, "wb").close()
            open(p2, "wb").close()
            session.add_image(p1, "input", make_active=True)
            session.add_image(p2, "input", make_active=True)
            tab.image_session = session

            tab._toggle_sim_ref()
            self.assertEqual(session.similarity_ref_index, session.current_index)

            tab._toggle_sim_ref()
            self.assertEqual(session.similarity_ref_index, -1)

    def test_calc_all_similarity_no_name_error_on_ref_only(self):
        tab = ImageCarousel.__new__(ImageCarousel)
        tab._sim_lock = mock.Mock()
        tab._sim_busy = False
        tab.after = lambda *_args, **_kwargs: None
        tab._sim_log = lambda *_args, **_kwargs: None
        tab.image_session = ImageSession()

        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "front.png")
            open(p1, "wb").close()
            tab.image_session.add_image(p1, "input", make_active=True)
            tab._calc_all_similarity(reason="test")


if __name__ == "__main__":
    unittest.main()
