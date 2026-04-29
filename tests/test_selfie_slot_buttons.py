import unittest

from kling_gui.tabs.selfie_tab import SelfieTab
from kling_gui.theme import BUTTON_FILLED_TEXT_COLOR, BUTTON_TEXT_COLOR, COLORS


class _FakeVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class _FakeButton:
    def __init__(self):
        self.config_calls = []

    def config(self, **kwargs):
        self.config_calls.append(kwargs)


class SelfieSlotButtonStyleTests(unittest.TestCase):
    def test_active_and_inactive_slot_colors_use_readable_theme_values(self):
        tab = SelfieTab.__new__(SelfieTab)
        tab._selfie_slot_var = _FakeVar(2)
        tab._slot_buttons = [_FakeButton(), _FakeButton(), _FakeButton()]

        tab._update_selfie_slot_button_colors()

        inactive_first = tab._slot_buttons[0].config_calls[-1]
        active_second = tab._slot_buttons[1].config_calls[-1]
        inactive_third = tab._slot_buttons[2].config_calls[-1]

        self.assertEqual(inactive_first["bg"], COLORS["bg_input"])
        self.assertEqual(inactive_first["fg"], BUTTON_TEXT_COLOR)
        self.assertEqual(active_second["bg"], COLORS["accent_blue"])
        self.assertEqual(active_second["fg"], BUTTON_FILLED_TEXT_COLOR)
        self.assertEqual(inactive_third["fg"], BUTTON_TEXT_COLOR)


if __name__ == "__main__":
    unittest.main()
