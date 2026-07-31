from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtNetwork import (
    QLocalServer,
    QLocalSocket,
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from . import __version__
from .library import LibraryStore
from .settings import application_settings
from .updates import (
    GITHUB_LATEST_RELEASE_API,
    GITHUB_RELEASES_URL,
    InstallerAsset,
    is_newer_version,
    windows_installer_asset,
)
from .vlc_runtime import configure_vlc_runtime, find_vlc_executable

VLC_RUNTIME_DIR = configure_vlc_runtime()

from .player import PlayerWindow  # noqa: E402 (VLC must be configured first on Windows)

BUILTIN_THEMES = {
    "dark": {
        "label": "Graphite",
        "window": "#101112",
        "panel": "#171819",
        "panel_alt": "#202224",
        "control": "#292b2d",
        "control_hover": "#35383a",
        "text": "#f0f0ef",
        "muted": "#a4a6a8",
        "border": "#414447",
        "accent": "#8f959a",
        "accent_hover": "#b1b5b8",
        "selection_text": "#111213",
    },
    "light": {
        "label": "Pearl",
        "window": "#c9cbc8",
        "panel": "#d7d8d5",
        "panel_alt": "#bfc2bf",
        "control": "#e2e3df",
        "control_hover": "#ced1cd",
        "text": "#252827",
        "muted": "#666b69",
        "border": "#a7aaa7",
        "accent": "#7b8b86",
        "accent_hover": "#64746f",
        "selection_text": "#ffffff",
    },
    "midnight": {
        "label": "Midnight",
        "window": "#07121e",
        "panel": "#0c1b2a",
        "panel_alt": "#11263a",
        "control": "#163149",
        "control_hover": "#1d405d",
        "text": "#e9f7ff",
        "muted": "#8fb1c6",
        "border": "#234760",
        "accent": "#37c8d8",
        "accent_hover": "#67dde8",
        "selection_text": "#031419",
    },
    "forest": {
        "label": "Forest",
        "window": "#0b1512",
        "panel": "#11211b",
        "panel_alt": "#172c24",
        "control": "#1c372d",
        "control_hover": "#27483c",
        "text": "#edf8f2",
        "muted": "#9ab9a9",
        "border": "#315244",
        "accent": "#69d39b",
        "accent_hover": "#8be3b4",
        "selection_text": "#082016",
    },
    "rose": {
        "label": "Rose",
        "window": "#171016",
        "panel": "#241720",
        "panel_alt": "#321f2b",
        "control": "#402736",
        "control_hover": "#543246",
        "text": "#fff1f7",
        "muted": "#c5a0b2",
        "border": "#5b384c",
        "accent": "#ee78a8",
        "accent_hover": "#f49ac0",
        "selection_text": "#2b0b18",
    },
    "sunset": {
        "label": "Sunset",
        "window": "#17120f",
        "panel": "#241b16",
        "panel_alt": "#32241c",
        "control": "#412e23",
        "control_hover": "#573c2c",
        "text": "#fff5eb",
        "muted": "#c5aa96",
        "border": "#604432",
        "accent": "#f39a5a",
        "accent_hover": "#ffb477",
        "selection_text": "#2b1305",
    },
    "pixie": {
        "label": "Pixie",
        "window": "#FBEFEF",
        "panel": "#FFE2E2",
        "panel_alt": "#F5CBCB",
        "control": "#FFF7F7",
        "control_hover": "#EEDBEA",
        "text": "#392F40",
        "muted": "#756779",
        "border": "#D5BBCD",
        "accent": "#C5B3D3",
        "accent_hover": "#B29CC3",
        "selection_text": "#2B2230",
    },
    "retro": {
        "label": "Retro",
        "window": "#000000",
        "panel": "#233D4D",
        "panel_alt": "#1A303D",
        "control": "#304E60",
        "control_hover": "#3C6073",
        "text": "#EAECF0",
        "muted": "#AAB8C0",
        "border": "#486778",
        "accent": "#FE7F2D",
        "accent_hover": "#FF9A5C",
        "selection_text": "#000000",
    },
    "space": {
        "label": "Space",
        "window": "#0B0909",
        "panel": "#2E4540",
        "panel_alt": "#243733",
        "control": "#38564F",
        "control_hover": "#408175",
        "text": "#F0F1FF",
        "muted": "#B5B9F0",
        "border": "#4D6A64",
        "accent": "#B5B9F0",
        "accent_hover": "#D0D3FF",
        "selection_text": "#0B0909",
    },
}


class AuroraApplication:
    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.settings = application_settings()
        self.library = LibraryStore()
        self.windows: list[PlayerWindow] = []
        self.themes = BUILTIN_THEMES
        self.vlc_executable = find_vlc_executable(VLC_RUNTIME_DIR)
        self._loaded_extensions: list[object] = []
        self.network = QNetworkAccessManager(qt_app)
        self._update_reply: QNetworkReply | None = None
        self._download_reply: QNetworkReply | None = None
        self._update_progress: QProgressDialog | None = None
        self._update_download_cancelled = False

    def start(
        self, media_locations: list[str], check_updates: bool = True
    ) -> None:
        selected_skin = str(self.settings.value("appearance/skin", "dark"))
        if selected_skin == "custom":
            custom_path = str(self.settings.value("appearance/custom_skin", ""))
            if custom_path and Path(custom_path).is_file():
                self.apply_custom_skin(custom_path)
            else:
                self.apply_skin("dark")
        else:
            self.apply_skin(selected_skin)
        self.load_extensions()
        self.open_locations(media_locations)
        if check_updates:
            QTimer.singleShot(2500, self._automatic_update_check)

    def open_locations(self, media_locations: list[str]) -> None:
        window = self.new_window()
        local_files = [path for path in media_locations if "://" not in path]
        if local_files:
            window.add_files(local_files)
        for location in media_locations:
            if "://" in location:
                window.open_in_available_pane(location)

    def new_window(self, path: str | None = None) -> PlayerWindow:
        if self.windows:
            window = self.windows[0]
            if path:
                if "://" in path:
                    window.open_in_available_pane(path)
                else:
                    window.add_files([path])
            window.raise_()
            window.activateWindow()
            return window
        window = PlayerWindow(self)
        self.windows.append(window)
        window.showMaximized()
        if path:
            window.add_files([path])
        return window

    def window_closed(self, window: PlayerWindow) -> None:
        if window in self.windows:
            self.windows.remove(window)
        if not self.windows:
            self.library.close()
            self.qt_app.exit(
                int(getattr(self.qt_app, "_aurora_exit_code", 0))
            )

    def apply_skin(self, name: str) -> None:
        palette = BUILTIN_THEMES.get(name)
        if palette:
            template = Path(__file__).parent / "skins" / "base.qss"
            if not template.exists():
                return
            stylesheet = template.read_text(encoding="utf-8")
            for key, value in palette.items():
                stylesheet = stylesheet.replace(f"@{key.upper()}@", value)
            self.qt_app.setStyleSheet(stylesheet)
            self.settings.setValue("appearance/skin", name)
            return
        skin = Path(__file__).parent / "skins" / f"{name}.qss"
        if not skin.exists():
            return
        self.qt_app.setStyleSheet(skin.read_text(encoding="utf-8"))
        self.settings.setValue("appearance/skin", name)

    def apply_custom_skin(self, path: str) -> None:
        try:
            stylesheet = Path(path).read_text(encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(None, "Skin", f"Could not load skin:\n{error}")
            return
        self.qt_app.setStyleSheet(stylesheet)
        self.settings.setValue("appearance/skin", "custom")
        self.settings.setValue("appearance/custom_skin", path)

    def set_automatic_updates(self, enabled: bool) -> None:
        self.settings.setValue("updates/automatic", enabled)

    def _automatic_update_check(self) -> None:
        enabled = (
            str(self.settings.value("updates/automatic", "true")).lower()
            == "true"
        )
        if not enabled:
            return
        last_check = float(self.settings.value("updates/last_check", 0) or 0)
        if time.time() - last_check >= 24 * 60 * 60:
            self.check_for_updates(manual=False)

    def check_for_updates(self, manual: bool = False) -> None:
        if self._update_reply is not None:
            if manual and self.windows:
                self.windows[0].statusBar().showMessage(
                    "An update check is already running.", 3000
                )
            return
        if manual and self.windows:
            self.windows[0].statusBar().showMessage(
                "Checking GitHub for updates…"
            )
        request = QNetworkRequest(QUrl(GITHUB_LATEST_RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(
            b"User-Agent", f"AuroraPlayer/{__version__}".encode("ascii")
        )
        reply = self.network.get(request)
        self._update_reply = reply
        reply.finished.connect(
            lambda current=reply, requested=manual: self._finish_update_check(
                current, requested
            )
        )
        QTimer.singleShot(
            10_000,
            lambda current=reply: (
                current.abort()
                if self._update_reply is current and current.isRunning()
                else None
            ),
        )

    def _finish_update_check(
        self, reply: QNetworkReply, manual: bool
    ) -> None:
        if self._update_reply is not reply:
            reply.deleteLater()
            return
        self._update_reply = None
        parent = self.windows[0] if self.windows else None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            error = reply.errorString()
            reply.deleteLater()
            if manual:
                QMessageBox.warning(
                    parent,
                    "Update check",
                    "Aurora Player could not check GitHub for updates.\n\n"
                    f"{error}",
                )
            return
        try:
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            latest_version = str(payload["tag_name"])
            release_url = str(payload.get("html_url", GITHUB_RELEASES_URL))
            installer_asset = windows_installer_asset(payload, latest_version)
        except (KeyError, TypeError, ValueError, UnicodeDecodeError):
            reply.deleteLater()
            if manual:
                QMessageBox.warning(
                    parent,
                    "Update check",
                    "GitHub returned an update response Aurora Player could not read.",
                )
            return
        reply.deleteLater()
        self.settings.setValue("updates/last_check", time.time())
        if not release_url.startswith(
            "https://github.com/AlexKav47/AuroraPlayer/"
        ):
            release_url = GITHUB_RELEASES_URL
        if is_newer_version(latest_version, __version__):
            message = QMessageBox(parent)
            message.setWindowTitle("Aurora Player update available")
            message.setIcon(QMessageBox.Icon.Information)
            message.setText(
                f"Aurora Player {latest_version.lstrip('v')} is available."
            )
            if sys.platform == "win32" and installer_asset is not None:
                message.setInformativeText(
                    f"You currently have version {__version__}. "
                    "Aurora Player can download and install the update for you."
                )
                install_button = message.addButton(
                    "Download and install",
                    QMessageBox.ButtonRole.AcceptRole,
                )
                message.addButton(QMessageBox.StandardButton.Cancel)
                message.setDefaultButton(install_button)
                message.exec()
                if message.clickedButton() is install_button:
                    self._download_and_install_update(
                        latest_version, installer_asset, release_url
                    )
            else:
                message.setInformativeText(
                    f"You currently have version {__version__}. "
                    "Open the GitHub release page to download it?"
                )
                message.setStandardButtons(
                    QMessageBox.StandardButton.Open
                    | QMessageBox.StandardButton.Cancel
                )
                message.setDefaultButton(QMessageBox.StandardButton.Open)
                if message.exec() == QMessageBox.StandardButton.Open:
                    QDesktopServices.openUrl(QUrl(release_url))
        elif manual:
            QMessageBox.information(
                parent,
                "Aurora Player is up to date",
                f"Version {__version__} is the latest available release.",
            )

    def _download_and_install_update(
        self,
        version: str,
        asset: InstallerAsset,
        release_url: str,
    ) -> None:
        parent = self.windows[0] if self.windows else None
        if self._download_reply is not None:
            if parent is not None:
                parent.statusBar().showMessage(
                    "An update is already downloading.", 3000
                )
            return
        request = QNetworkRequest(QUrl(asset.url))
        request.setRawHeader(b"Accept", b"application/octet-stream")
        request.setRawHeader(
            b"User-Agent", f"AuroraPlayer/{__version__}".encode("ascii")
        )
        reply = self.network.get(request)
        self._download_reply = reply
        self._update_download_cancelled = False
        progress = QProgressDialog(
            f"Downloading Aurora Player {version.lstrip('v')}â€¦",
            "Cancel",
            0,
            100,
            parent,
        )
        progress.setWindowTitle("Aurora Player update")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        self._update_progress = progress
        progress.canceled.connect(self._cancel_update_download)
        reply.downloadProgress.connect(self._set_update_download_progress)
        reply.finished.connect(
            lambda current=reply, update_version=version,
            update_asset=asset, fallback=release_url: (
                self._finish_update_download(
                    current, update_version, update_asset, fallback
                )
            )
        )
        QTimer.singleShot(
            10 * 60 * 1000,
            lambda current=reply: (
                current.abort()
                if self._download_reply is current and current.isRunning()
                else None
            ),
        )

    def _set_update_download_progress(
        self, received: int, total: int
    ) -> None:
        progress = self._update_progress
        if progress is None:
            return
        if total <= 0:
            progress.setRange(0, 0)
            return
        progress.setRange(0, total)
        progress.setValue(received)

    def _cancel_update_download(self) -> None:
        self._update_download_cancelled = True
        if self._download_reply is not None:
            self._download_reply.abort()

    def _finish_update_download(
        self,
        reply: QNetworkReply,
        version: str,
        asset: InstallerAsset,
        release_url: str,
    ) -> None:
        if self._download_reply is not reply:
            reply.deleteLater()
            return
        self._download_reply = None
        progress = self._update_progress
        self._update_progress = None
        if progress is not None:
            progress.close()
            progress.deleteLater()
        parent = self.windows[0] if self.windows else None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            error = reply.errorString()
            reply.deleteLater()
            if not self._update_download_cancelled:
                QMessageBox.warning(
                    parent,
                    "Update download",
                    "Aurora Player could not download the update.\n\n"
                    f"{error}",
                )
            return
        contents = bytes(reply.readAll())
        reply.deleteLater()
        actual_sha256 = hashlib.sha256(contents).hexdigest()
        if asset.sha256 is not None and actual_sha256 != asset.sha256:
            QMessageBox.critical(
                parent,
                "Update verification failed",
                "The downloaded installer did not match GitHub's SHA-256 "
                "digest and will not be opened.",
            )
            return
        update_root = Path(tempfile.gettempdir()) / "AuroraPlayerUpdates"
        try:
            update_root.mkdir(parents=True, exist_ok=True)
            installer_path = update_root / asset.name
            partial_path = update_root / f"{asset.name}.download"
            partial_path.write_bytes(contents)
            os.replace(partial_path, installer_path)
        except OSError as error:
            QMessageBox.warning(
                parent,
                "Update download",
                "Aurora Player could not save the update installer.\n\n"
                f"{error}",
            )
            return
        parameters = " ".join(
            [
                "/SILENT",
                "/SUPPRESSMSGBOXES",
                "/CLOSEAPPLICATIONS",
                "/RESTARTAPPLICATIONS",
            ]
        )
        try:
            shell_execute = ctypes.windll.shell32.ShellExecuteW
            shell_execute.argtypes = [
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_int,
            ]
            shell_execute.restype = ctypes.c_void_p
            result = shell_execute(
                None,
                "runas",
                str(installer_path),
                parameters,
                str(installer_path.parent),
                1,
            )
            started = int(result or 0) > 32
        except (AttributeError, OSError, TypeError, ValueError):
            started = False
        if not started:
            choice = QMessageBox.warning(
                parent,
                "Update installer",
                "The update was downloaded but Windows could not start the "
                "installer. Open the GitHub release page instead?",
                QMessageBox.StandardButton.Open
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Open,
            )
            if choice == QMessageBox.StandardButton.Open:
                QDesktopServices.openUrl(QUrl(release_url))
            return
        if parent is not None:
            parent.statusBar().showMessage(
                f"Installing Aurora Player {version.lstrip('v')}â€¦"
            )

    def load_extensions(self) -> None:
        locations = [Path(__file__).parent / "extensions"]
        portable_root = os.environ.get("AURORA_DATA_DIR")
        user_root = (
            Path(portable_root).expanduser().resolve()
            if portable_root
            else Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppDataLocation
                )
            )
        )
        user_extensions = user_root / "extensions"
        user_extensions.mkdir(parents=True, exist_ok=True)
        locations.append(user_extensions)
        for root in locations:
            if not root.exists():
                continue
            for path in root.glob("*.py"):
                if path.name.startswith("_"):
                    continue
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"aurora_extension_{path.stem}_{abs(hash(path))}", path
                    )
                    if spec is None or spec.loader is None:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    register = getattr(module, "register", None)
                    if callable(register):
                        register(self)
                        self._loaded_extensions.append(module)
                except Exception as error:
                    print(f"Extension {path.name} failed: {error}", file=sys.stderr)


def parse_args(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aurora Player")
    parser.add_argument(
        "media",
        nargs="*",
        help="Media file paths or URLs; up to four open in one window",
    )
    parser.add_argument("--self-test", metavar="MEDIA", help=argparse.SUPPRESS)
    parser.add_argument(
        "--pane-close-test", metavar="MEDIA", help=argparse.SUPPRESS
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    namespace = parse_args(sys.argv[1:] if arguments is None else arguments)
    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("Aurora Player")
    qt_app.setApplicationDisplayName("Aurora Player")
    qt_app.setOrganizationName("AuroraPlayer")
    qt_app.setStyle("Fusion")
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        qt_app.setWindowIcon(QIcon(str(logo_path)))
    media = [
        value
        if "://" in value
        else str(Path(value).expanduser().resolve())
        for value in namespace.media
    ]
    if not namespace.self_test and not namespace.pane_close_test:
        instance_name = "AuroraPlayer-SingleWindow-v1"
        client = QLocalSocket()
        client.connectToServer(instance_name)
        if client.waitForConnected(300):
            client.write(json.dumps({"media": media}).encode("utf-8"))
            client.flush()
            client.waitForBytesWritten(1000)
            client.disconnectFromServer()
            return 0

    controller = AuroraApplication(qt_app)
    if namespace.self_test or namespace.pane_close_test:
        pane_close_test = bool(namespace.pane_close_test)
        test_argument = namespace.pane_close_test or namespace.self_test
        test_media = str(Path(test_argument).expanduser().resolve())
        test_root = Path(
            os.environ.get(
                "AURORA_DATA_DIR",
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.TempLocation
                ),
            )
        )
        test_root.mkdir(parents=True, exist_ok=True)
        result_path = test_root / (
            "pane-close-test-result.json"
            if pane_close_test
            else "self-test-result.json"
        )
        qt_app.setQuitOnLastWindowClosed(False)
        controller.start([test_media] * 4, check_updates=False)

        def finish_self_test() -> None:
            exit_code = 1
            result: dict[str, object] = {"media": test_media}
            try:
                window = controller.windows[0]
                result["pane_count"] = len(window.panes)
                result["lengths_ms"] = [
                    pane.player.get_length() for pane in window.panes
                ]
                result["times_ms"] = [
                    pane.player.get_time() for pane in window.panes
                ]
                expected_panes = 2 if pane_close_test else 4
                result["completed_pane_cleanups"] = (
                    window._completed_pane_cleanups
                )
                passed = (
                    len(window.panes) == expected_panes
                    and all(pane.path == test_media for pane in window.panes)
                    and all(
                        pane.player.get_length() > 0
                        and pane.player.get_time() >= 0
                        for pane in window.panes
                    )
                    and (
                        not pane_close_test
                        or window._completed_pane_cleanups >= 2
                    )
                )
                result["passed"] = passed
                exit_code = 0 if passed else 1
            except Exception:
                result["passed"] = False
                result["error"] = traceback.format_exc()
            finally:
                result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                qt_app._aurora_exit_code = exit_code
                for open_window in list(controller.windows):
                    open_window.close()

        if pane_close_test:
            def close_playing_pane() -> None:
                window = controller.windows[0]
                if len(window.panes) > 2:
                    window.close_pane(window.panes[-1])

            QTimer.singleShot(900, close_playing_pane)
            QTimer.singleShot(1200, close_playing_pane)
            QTimer.singleShot(2600, finish_self_test)
        else:
            QTimer.singleShot(1500, finish_self_test)
        qt_app._aurora_controller = controller
        return qt_app.exec()

    server = QLocalServer(qt_app)
    QLocalServer.removeServer("AuroraPlayer-SingleWindow-v1")
    server.listen("AuroraPlayer-SingleWindow-v1")

    def accept_instance_message() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if not connection.bytesAvailable():
                connection.waitForReadyRead(1000)
            try:
                payload = json.loads(bytes(connection.readAll()).decode("utf-8"))
                locations = [str(item) for item in payload.get("media", [])]
                controller.open_locations(locations)
            except (ValueError, TypeError, UnicodeDecodeError):
                pass
            connection.disconnectFromServer()

    server.newConnection.connect(accept_instance_message)
    controller.start(media)
    qt_app._aurora_controller = controller  # Keep controller alive for the event loop.
    qt_app._aurora_server = server
    return qt_app.exec()
