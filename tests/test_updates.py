from aurora_player.updates import (
    InstallerAsset,
    is_newer_version,
    version_key,
    windows_installer_asset,
)


def test_version_key_accepts_github_tags() -> None:
    assert version_key("v1.2.3") == (1, 2, 3)
    assert version_key("Aurora Player 2.0") == (2, 0)


def test_newer_version_comparison_normalizes_missing_components() -> None:
    assert is_newer_version("v1.1.0", "1.0.0")
    assert not is_newer_version("v1.0", "1.0.0")
    assert not is_newer_version("unknown", "1.0.0")


def test_windows_installer_asset_requires_the_official_versioned_download() -> None:
    digest = "ab" * 32
    release = {
        "assets": [
            {
                "name": "AuroraPlayer-v1.3.0-Setup.exe",
                "browser_download_url": (
                    "https://github.com/AlexKav47/AuroraPlayer/releases/"
                    "download/v1.3.0/AuroraPlayer-v1.3.0-Setup.exe"
                ),
                "digest": f"sha256:{digest}",
            }
        ]
    }

    assert windows_installer_asset(release, "v1.3.0") == InstallerAsset(
        name="AuroraPlayer-v1.3.0-Setup.exe",
        url=(
            "https://github.com/AlexKav47/AuroraPlayer/releases/"
            "download/v1.3.0/AuroraPlayer-v1.3.0-Setup.exe"
        ),
        sha256=digest,
    )
    assert windows_installer_asset(release, "v1.4.0") is None


def test_windows_installer_asset_rejects_untrusted_download_urls() -> None:
    release = {
        "assets": [
            {
                "name": "AuroraPlayer-v2.0.0-Setup.exe",
                "browser_download_url": (
                    "https://example.com/AuroraPlayer-v2.0.0-Setup.exe"
                ),
            }
        ]
    }

    assert windows_installer_asset(release, "v2.0.0") is None
