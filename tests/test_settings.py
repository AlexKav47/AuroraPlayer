from pathlib import Path

from aurora_player.settings import application_settings


def test_portable_settings_use_an_ini_file(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AURORA_DATA_DIR", str(tmp_path))
    settings = application_settings()
    settings.setValue("shortcuts/play_pause", "P")
    settings.sync()

    assert Path(settings.fileName()) == tmp_path / "settings.ini"
    assert settings.value("shortcuts/play_pause") == "P"
