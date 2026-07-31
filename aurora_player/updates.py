from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


GITHUB_LATEST_RELEASE_API = (
    "https://api.github.com/repos/AlexKav47/AuroraPlayer/releases/latest"
)
GITHUB_RELEASES_URL = "https://github.com/AlexKav47/AuroraPlayer/releases"
GITHUB_DOWNLOAD_PREFIX = (
    "https://github.com/AlexKav47/AuroraPlayer/releases/download/"
)


@dataclass(frozen=True)
class InstallerAsset:
    name: str
    url: str
    sha256: str | None = None


def version_key(value: str) -> tuple[int, ...]:
    """Return a practical comparison key for release tags such as v1.2.3."""
    match = re.search(r"\d+(?:\.\d+)*", value)
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(0).split("."))


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_key = version_key(candidate)
    current_key = version_key(current)
    if not candidate_key or not current_key:
        return False
    length = max(len(candidate_key), len(current_key))
    return candidate_key + (0,) * (length - len(candidate_key)) > current_key + (
        0,
    ) * (length - len(current_key))


def windows_installer_asset(
    release: dict[str, Any], release_tag: str
) -> InstallerAsset | None:
    """Return the official installer asset for a GitHub release, if present."""
    version = version_key(release_tag)
    if not version:
        return None
    expected_name = (
        f"AuroraPlayer-v{'.'.join(str(part) for part in version)}-Setup.exe"
    )
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        return None
    for value in assets:
        if not isinstance(value, dict):
            continue
        name = str(value.get("name", ""))
        url = str(value.get("browser_download_url", ""))
        if name.casefold() != expected_name.casefold():
            continue
        if not url.startswith(GITHUB_DOWNLOAD_PREFIX):
            continue
        digest = str(value.get("digest", ""))
        sha256 = None
        if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            sha256 = digest.split(":", 1)[1].lower()
        return InstallerAsset(name=name, url=url, sha256=sha256)
    return None
