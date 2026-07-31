from pathlib import Path

from aurora_player.settings import (
    application_settings,
    playback_skip_seconds,
    set_playback_skip_seconds,
)


def test_portable_settings_use_an_ini_file(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AURORA_DATA_DIR", str(tmp_path))
    settings = application_settings()
    settings.setValue("shortcuts/play_pause", "P")
    settings.sync()

    assert Path(settings.fileName()) == tmp_path / "settings.ini"
    assert settings.value("shortcuts/play_pause") == "P"


def test_playback_skip_amount_defaults_validates_and_persists(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AURORA_DATA_DIR", str(tmp_path))
    settings = application_settings()

    assert playback_skip_seconds(settings) == 10

    set_playback_skip_seconds(settings, 25)
    assert playback_skip_seconds(application_settings()) == 25

    settings.setValue("playback/skip_seconds", 12)
    assert playback_skip_seconds(settings) == 10
