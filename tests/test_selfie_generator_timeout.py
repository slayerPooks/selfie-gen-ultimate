import unittest

from selfie_generator import SelfieGenerator


class SelfieGeneratorTimeoutTests(unittest.TestCase):
    def test_default_timeout_when_missing_or_invalid(self):
        self.assertEqual(SelfieGenerator.sanitize_poll_timeout_seconds(None), 300)
        self.assertEqual(SelfieGenerator.sanitize_poll_timeout_seconds("bad"), 300)

    def test_timeout_bounds_are_clamped(self):
        self.assertEqual(SelfieGenerator.sanitize_poll_timeout_seconds(5), 60)
        self.assertEqual(SelfieGenerator.sanitize_poll_timeout_seconds(7200), 1800)

    def test_timeout_within_bounds_is_kept(self):
        self.assertEqual(SelfieGenerator.sanitize_poll_timeout_seconds(420), 420)


if __name__ == "__main__":
    unittest.main()
