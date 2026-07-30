from aurora_player.updates import is_newer_version, version_key


def test_version_key_accepts_github_tags() -> None:
    assert version_key("v1.2.3") == (1, 2, 3)
    assert version_key("Aurora Player 2.0") == (2, 0)


def test_newer_version_comparison_normalizes_missing_components() -> None:
    assert is_newer_version("v1.1.0", "1.0.0")
    assert not is_newer_version("v1.0", "1.0.0")
    assert not is_newer_version("unknown", "1.0.0")
