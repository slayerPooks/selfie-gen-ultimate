from kling_gui.drop_zone import parse_dnd_paths


def test_parse_dnd_paths_single_path():
    path = "/tmp/test-image.png"
    result = parse_dnd_paths(path, splitlist_fn=None, require_exists=False)
    assert result == [path]


def test_parse_dnd_paths_multiple_with_spaces_and_braces():
    data = "{/Users/me/My Pics/a one.png} {/Users/me/b-two.jpg}"
    result = parse_dnd_paths(data, splitlist_fn=None, require_exists=False)
    assert result == ["/Users/me/My Pics/a one.png", "/Users/me/b-two.jpg"]


def test_parse_dnd_paths_prefers_tk_splitlist():
    data = "{ignored value}"

    def splitlist_fn(_payload):
        return ("/x/one.png", "/x/two with space.jpg")

    result = parse_dnd_paths(data, splitlist_fn=splitlist_fn, require_exists=False)
    assert result == ["/x/one.png", "/x/two with space.jpg"]


def test_parse_dnd_paths_splitlist_fallback_on_error():
    data = "{/x/a.png} /x/b.png"

    def splitlist_fn(_payload):
        raise RuntimeError("bad parser")

    result = parse_dnd_paths(data, splitlist_fn=splitlist_fn, require_exists=False)
    assert result == ["/x/a.png", "/x/b.png"]
