from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtNetwork import (
    QLocalServer,
    QLocalSocket,
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .library import LibraryStore
from .settings import application_settings
from .updates import (
    GITHUB_LATEST_RELEASE_API,
    GITHUB_RELEASES_URL,
    is_newer_version,
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

    def start(self, media_locations: list[str]) -> None:
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
            self.qt_app.quit()

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
    if not namespace.self_test:
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
    if namespace.self_test:
        test_media = str(Path(namespace.self_test).expanduser().resolve())
        test_root = Path(
            os.environ.get(
                "AURORA_DATA_DIR",
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.TempLocation
                ),
            )
        )
        test_root.mkdir(parents=True, exist_ok=True)
        result_path = test_root / "self-test-result.json"
        qt_app.setQuitOnLastWindowClosed(False)
        controller.start([test_media] * 4)

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
                passed = (
                    len(window.panes) == 4
                    and all(pane.path == test_media for pane in window.panes)
                    and all(
                        pane.player.get_length() > 0
                        and pane.player.get_time() >= 0
                        for pane in window.panes
                    )
                )
                result["passed"] = passed
                exit_code = 0 if passed else 1
            except Exception:
                result["passed"] = False
                result["error"] = traceback.format_exc()
            finally:
                result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                for open_window in list(controller.windows):
                    open_window.close()
                qt_app.exit(exit_code)

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
