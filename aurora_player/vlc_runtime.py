from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_DLL_DIRECTORY_HANDLES: list[object] = []


def configure_vlc_runtime() -> Path | None:
    """Find an embedded engine first, then fall back to a normal installation."""
    if sys.platform != "win32":
        return None

    candidates: list[Path] = []
    configured = os.environ.get("AURORA_VLC_DIR")
    if configured:
        candidates.append(Path(configured).expanduser())

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "vlc")

    executable_root = Path(sys.executable).resolve().parent
    candidates.append(executable_root / "vlc")
    if not getattr(sys, "frozen", False):
        candidates.extend(
            [
            Path(__file__).resolve().parent.parent / "runtime" / "vlc",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            / "VideoLAN"
            / "VLC",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "VideoLAN"
            / "VLC",
            ]
        )
    for directory in candidates:
        if (directory / "libvlc.dll").exists():
            plugin_directory = directory / "plugins"
            os.environ["VLC_PLUGIN_PATH"] = str(plugin_directory)
            os.environ["PYTHON_VLC_MODULE_PATH"] = str(plugin_directory)
            os.environ["PYTHON_VLC_LIB_PATH"] = str(directory / "libvlc.dll")
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(directory)))
            return directory.resolve()
    return None


def find_vlc_executable(runtime_dir: Path | None = None) -> str | None:
    if sys.platform == "win32" and runtime_dir:
        executable = runtime_dir / "vlc.exe"
        if executable.exists():
            return str(executable)
    return shutil.which("cvlc") or shutil.which("vlc")
