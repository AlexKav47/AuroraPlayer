from __future__ import annotations

import re


GITHUB_LATEST_RELEASE_API = (
    "https://api.github.com/repos/AlexKav47/AuroraPlayer/releases/latest"
)
GITHUB_RELEASES_URL = "https://github.com/AlexKav47/AuroraPlayer/releases"


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
