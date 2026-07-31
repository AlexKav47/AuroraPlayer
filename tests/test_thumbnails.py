import os
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from aurora_player.thumbnails import (
    THUMBNAIL_SIZE,
    media_placeholder,
    thumbnail_cache_directory,
    thumbnail_cache_key,
)


def _application() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def test_thumbnail_key_changes_with_file(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"first")
    first = thumbnail_cache_key(media)
    media.write_bytes(b"different contents")
    second = thumbnail_cache_key(media)

    assert len(first) == 64
    assert first != second


def test_placeholder_has_expected_dimensions() -> None:
    app = _application()
    video = media_placeholder("example.mkv")
    audio = media_placeholder("example.flac", QSize(80, 45))

    assert app is not None
    assert video.size() == THUMBNAIL_SIZE
    assert audio.size() == QSize(80, 45)
    assert not video.isNull() and not audio.isNull()


def test_portable_thumbnail_cache_stays_in_data_directory(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("AURORA_DATA_DIR", str(tmp_path))
    assert thumbnail_cache_directory() == tmp_path / "thumbnails"
