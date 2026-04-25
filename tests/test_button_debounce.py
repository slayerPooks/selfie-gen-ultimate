import time

from kling_gui.theme import debounce_command


def test_debounce_blocks_rapid_repeat_calls():
    calls = []

    def handler():
        calls.append("x")

    wrapped = debounce_command(handler, key="test_debounce_blocks", interval_ms=180)
    wrapped()
    wrapped()

    assert len(calls) == 1


def test_debounce_allows_call_after_interval():
    calls = []

    def handler():
        calls.append("x")

    wrapped = debounce_command(handler, key="test_debounce_allows", interval_ms=120)
    wrapped()
    time.sleep(0.16)
    wrapped()

    assert len(calls) == 2
