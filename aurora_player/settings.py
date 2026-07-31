from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings


SKIP_SECONDS_OPTIONS = (5, 10, 25, 50)
DEFAULT_SKIP_SECONDS = 10


def application_settings() -> QSettings:
    portable_root = os.environ.get("AURORA_DATA_DIR")
    if portable_root:
        root = Path(portable_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return QSettings(
            str(root / "settings.ini"), QSettings.Format.IniFormat
        )
    return QSettings("AuroraPlayer", "AuroraPlayer")


def playback_skip_seconds(settings: QSettings) -> int:
    value = settings.value("playback/skip_seconds", DEFAULT_SKIP_SECONDS)
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SKIP_SECONDS
    if seconds not in SKIP_SECONDS_OPTIONS:
        return DEFAULT_SKIP_SECONDS
    return seconds


def set_playback_skip_seconds(settings: QSettings, seconds: int) -> int:
    seconds = int(seconds)
    if seconds not in SKIP_SECONDS_OPTIONS:
        raise ValueError(f"Unsupported playback skip interval: {seconds}")
    settings.setValue("playback/skip_seconds", seconds)
    settings.sync()
    return seconds
