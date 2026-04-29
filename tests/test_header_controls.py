from pathlib import Path
import unittest


class HeaderControlsTests(unittest.TestCase):
    def test_header_uses_sessions_button_without_duplicate_load_session(self):
        src = Path("kling_gui/main_window.py").read_text(encoding="utf-8")
        self.assertIn('text="Sessions"', src)
        self.assertNotIn('text="Load Session"', src)
        self.assertNotIn('text="Add Image"', src)


if __name__ == "__main__":
    unittest.main()
