from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings


def application_settings() -> QSettings:
    portable_root = os.environ.get("AURORA_DATA_DIR")
    if portable_root:
        root = Path(portable_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return QSettings(
            str(root / "settings.ini"), QSettings.Format.IniFormat
        )
    return QSettings("AuroraPlayer", "AuroraPlayer")
