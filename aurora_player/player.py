from __future__ import annotations

import os
import queue
import random
import sys
import threading
import ctypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

import vlc
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QImage,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QTabWidget,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .dialogs import (
    AudioEffectsDialog,
    ConverterDialog,
    DiscDialog,
    ShortcutEditorDialog,
    SubtitleStyleDialog,
    SyncDialog,
    VideoEffectsDialog,
)
from . import __version__
from .library import LibraryStore, expand_media_paths, load_m3u, save_m3u
from .settings import (
    SKIP_SECONDS_OPTIONS,
    application_settings,
    playback_skip_seconds,
    set_playback_skip_seconds,
)
from .thumbnails import THUMBNAIL_SIZE, ThumbnailProvider, media_placeholder

if TYPE_CHECKING:
    from .app import AuroraApplication


SHORTCUT_DEFINITIONS: dict[str, tuple[str, str]] = {
    "open_files": ("Open file(s)", "Ctrl+O"),
    "open_folder": ("Open folder", "Ctrl+Shift+O"),
    "open_disc": ("Open disc", "Ctrl+D"),
    "open_url": ("Open network URL", "Ctrl+L"),
    "add_pane": ("Add video pane", "Ctrl+N"),
    "convert": ("Convert or transcode", "Ctrl+R"),
    "save_playlist": ("Save playlist", "Ctrl+S"),
    "close_window": ("Close window", "Ctrl+W"),
    "play_pause": ("Play or pause active pane", "Space"),
    "play_pause_all": ("Play or pause all panes", "Ctrl+Space"),
    "stop": ("Stop", "S"),
    "shuffle_playlist": ("Shuffle playlist", "Ctrl+H"),
    "shuffle_library": ("Shuffle media library", "Ctrl+Shift+H"),
    "next_frame": ("Next frame", "E"),
    "set_a": ("Set A loop point", "["),
    "set_b": ("Set B loop point", "]"),
    "clear_ab": ("Clear A–B loop", "\\"),
    "seek_back_5": ("Skip backward by the selected amount", "Left"),
    "seek_forward_5": ("Skip forward by the selected amount", "Right"),
    "seek_back_30": ("Seek backward 30 seconds", "Shift+Left"),
    "seek_forward_30": ("Seek forward 30 seconds", "Shift+Right"),
    "volume_up": ("Volume up", "Up"),
    "volume_down": ("Volume down", "Down"),
    "mute": ("Mute", "M"),
    "fullscreen": ("Enter or leave fullscreen", "F11"),
    "fullscreen_alternate": ("Fullscreen alternate", "Ctrl+F"),
    "leave_fullscreen": ("Leave fullscreen", "Esc"),
    "close_pane": ("Close active pane", "Ctrl+Shift+W"),
    "toggle_sidebar": ("Show or hide sidebar", "Ctrl+B"),
}


def format_time(milliseconds: int) -> str:
    if milliseconds < 0:
        milliseconds = 0
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def decode_label(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


class InteractiveSlider(QSlider):
    value_selected = Signal(int)
    interaction_started = Signal()
    interaction_finished = Signal()

    def __init__(
        self,
        orientation: Qt.Orientation,
        value_formatter: Callable[[int], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self._value_formatter = value_formatter
        self._mouse_down = False
        self.setMouseTracking(True)

    def _value_at(self, event) -> int:
        if self.orientation() == Qt.Orientation.Horizontal:
            coordinate = event.position().x()
            span = max(1, self.width() - 1)
        else:
            coordinate = self.height() - 1 - event.position().y()
            span = max(1, self.height() - 1)
        ratio = max(0.0, min(1.0, coordinate / span))
        if self.invertedAppearance():
            ratio = 1.0 - ratio
        return round(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def _show_hover_value(self, event, value: int) -> None:
        QToolTip.showText(
            event.globalPosition().toPoint(),
            self._value_formatter(value),
            self,
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_down = True
            self.setFocus()
            value = self._value_at(event)
            self.setValue(value)
            self._show_hover_value(event, value)
            self.interaction_started.emit()
            self.value_selected.emit(value)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        value = self._value_at(event)
        self._show_hover_value(event, value)
        if self._mouse_down:
            self.setValue(value)
            self.value_selected.emit(value)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._mouse_down:
            value = self._value_at(event)
            self.setValue(value)
            self.value_selected.emit(value)
            self._mouse_down = False
            self.interaction_finished.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._mouse_down:
            QToolTip.hideText()
        super().leaveEvent(event)


class VideoSurface(QWidget):
    files_dropped = Signal(list)
    toggle_fullscreen = Signal()
    seek_gesture = Signal(int)
    volume_gesture = Signal(int)
    activated = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background: #000;")
        self.setAcceptDrops(True)
        self.setMinimumSize(480, 270)
        self._gesture_origin = None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_fullscreen.emit()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        if event.button() == Qt.MouseButton.RightButton:
            self._gesture_origin = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.RightButton
            and self._gesture_origin is not None
        ):
            delta = event.position() - self._gesture_origin
            self._gesture_origin = None
            if abs(delta.x()) > abs(delta.y()) and abs(delta.x()) > 35:
                self.seek_gesture.emit(10_000 if delta.x() > 0 else -10_000)
            elif abs(delta.y()) > 35:
                self.volume_gesture.emit(5 if delta.y() < 0 else -5)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MediaDropArea(QWidget):
    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setToolTip("Drop video or audio files and folders here")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class FullWidthTabWidget(QTabWidget):
    """Keep sidebar tab headings evenly spread across the entire dock."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tabBar().setExpanding(True)
        self.tabBar().setUsesScrollButtons(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # QTabWidget otherwise gives QTabBar only its contents' size hint on
        # Windows, leaving unused space after the Library heading.
        self.tabBar().setFixedWidth(event.size().width())


@dataclass(slots=True)
class MediaPane:
    container: QWidget
    header: QWidget
    surface: VideoSurface
    title_label: QLabel
    play_button: QPushButton
    close_button: QPushButton
    instance: vlc.Instance
    player: vlc.MediaPlayer
    path: str | None = None
    end_advanced: bool = False
    last_resume_write: float = 0.0


class SerialVlcCleanup:
    """Release native VLC objects in order, away from the Qt interface thread."""

    def __init__(self) -> None:
        self._jobs: queue.Queue[
            tuple[str, object, Callable[[], None] | None]
        ] = queue.Queue()
        self._thread = threading.Thread(
            target=self._run,
            name="aurora-vlc-cleanup",
            daemon=True,
        )
        self._thread.start()

    def release_player(
        self,
        player: vlc.MediaPlayer,
        finished: Callable[[], None] | None = None,
    ) -> None:
        self._jobs.put(("player", player, finished))

    def finish(
        self,
        instance: vlc.Instance,
        finished: Callable[[], None],
    ) -> None:
        self._jobs.put(("instance", instance, finished))

    def _run(self) -> None:
        while True:
            kind, target, finished = self._jobs.get()
            try:
                if kind == "player":
                    try:
                        target.stop()
                    finally:
                        target.release()
                else:
                    target.release()
            except Exception:
                pass
            finally:
                if finished is not None:
                    try:
                        finished()
                    except Exception:
                        pass
                self._jobs.task_done()
            if kind == "instance":
                return


class PlayerWindow(QMainWindow):
    cleanup_finished = Signal()
    pane_cleanup_finished = Signal(object)

    def __init__(
        self,
        application: "AuroraApplication",
        initial_media: str | None = None,
    ) -> None:
        super().__init__()
        self.application_controller = application
        self.settings = application_settings()
        self._skip_seconds = playback_skip_seconds(self.settings)
        self.library = application.library
        self.panes: list[MediaPane] = []
        self.shortcut_actions: dict[str, QAction] = {}
        self._vlc_cleanup = SerialVlcCleanup()
        self._completed_pane_cleanups = 0
        self._vlc_instance = self._create_vlc_instance()
        self.active_pane = self._create_pane()
        self._slider_dragging = False
        self._ab_start: int | None = None
        self._ab_end: int | None = None
        self._audio_delay_ms = 0
        self._subtitle_delay_ms = 0
        self._audio_filters: tuple[bool, bool] = (False, False)
        self._equalizer = None
        self._sharpen = 0.0
        self._fullscreen = False
        self._fullscreen_controls_visible = False
        self._fullscreen_cursor_position = QCursor.pos()
        self._controls_animation: QPropertyAnimation | None = None
        self._window_was_maximized = True
        self._sidebar_was_visible = True
        self._pane_mouse_was_down = False
        self._dialogs: list[QWidget] = []
        self._cleanup_started = False
        self._cleanup_done = False
        self.thumbnail_provider = ThumbnailProvider(self)
        self.thumbnail_provider.ready.connect(self._apply_thumbnail)
        self.cleanup_finished.connect(self._complete_close)
        self.pane_cleanup_finished.connect(self._finalize_closed_pane)

        self.setWindowTitle("Aurora Player")
        self.resize(1180, 720)
        self.setAcceptDrops(True)
        self._build_ui()
        self._build_menus()
        self._bind_shortcuts()
        self._attach_video_output()

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._update_playback)

        # libVLC renders into a native child window on Windows. That child can
        # receive the click before Qt's VideoSurface does, so also watch the
        # physical left-button transition and resolve it against pane geometry.
        self.pane_selection_timer = QTimer(self)
        self.pane_selection_timer.setInterval(25)
        self.pane_selection_timer.timeout.connect(self._poll_pane_selection)
        self.pane_selection_timer.start()

        self.fullscreen_activity_timer = QTimer(self)
        self.fullscreen_activity_timer.setInterval(100)
        self.fullscreen_activity_timer.timeout.connect(
            self._poll_fullscreen_activity
        )
        self.fullscreen_hide_timer = QTimer(self)
        self.fullscreen_hide_timer.setSingleShot(True)
        self.fullscreen_hide_timer.setInterval(3000)
        self.fullscreen_hide_timer.timeout.connect(
            self._hide_fullscreen_controls
        )
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

        if initial_media:
            QTimer.singleShot(0, lambda: self.open_media(initial_media))

    @property
    def player(self) -> vlc.MediaPlayer:
        return self.active_pane.player

    @property
    def vlc_instance(self) -> vlc.Instance:
        return self._vlc_instance

    @property
    def current_path(self) -> str | None:
        return self.active_pane.path

    @current_path.setter
    def current_path(self, value: str | None) -> None:
        self.active_pane.path = value

    @property
    def video(self) -> VideoSurface:
        return self.active_pane.surface

    def _create_vlc_instance(self) -> vlc.Instance:
        options = [
            "--no-video-title-show",
            "--no-mouse-events",
            "--quiet",
            "--no-snapshot-preview",
        ]
        if sys.platform == "win32":
            # VLC's default MMDevice output can deadlock while a playing pane
            # is torn down. DirectSound uses the normal Windows mixer without
            # the failing libmmdevice shutdown path.
            options.append("--aout=directsound")
        instance = vlc.Instance(*options)
        if instance is None:
            raise RuntimeError("The embedded media engine could not be initialized.")
        return instance

    def _create_pane(self) -> MediaPane:
        instance = self._vlc_instance
        container = QWidget()
        container.setObjectName("mediaPane")
        pane_layout = QVBoxLayout(container)
        pane_layout.setContentsMargins(3, 3, 3, 3)
        pane_layout.setSpacing(3)
        pane_header = QWidget()
        pane_header.setFixedHeight(30)
        header_layout = QHBoxLayout(pane_header)
        header_layout.setContentsMargins(7, 2, 4, 2)
        title_label = QLabel("Empty video pane")
        title_label.setToolTip("Click the video to select this pane")
        play_button = QPushButton()
        play_button.setFixedSize(30, 24)
        play_button.setToolTip("Play or pause this video")
        close_button = QPushButton("×")
        close_button.setFixedSize(28, 24)
        close_button.setToolTip("Close this video pane")
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(play_button)
        header_layout.addWidget(close_button)
        surface = VideoSurface()
        surface.setToolTip(
            "Click to select this video; double-click for fullscreen"
        )
        pane_layout.addWidget(pane_header)
        pane_layout.addWidget(surface, 1)
        pane = MediaPane(
            container=container,
            header=pane_header,
            surface=surface,
            title_label=title_label,
            play_button=play_button,
            close_button=close_button,
            instance=instance,
            player=instance.media_player_new(),
        )
        pane.surface.files_dropped.connect(
            lambda paths, target=pane: self.add_dropped_paths(paths, target)
        )
        pane.surface.toggle_fullscreen.connect(self.toggle_fullscreen)
        pane.surface.seek_gesture.connect(self._seek_from_gesture)
        pane.surface.volume_gesture.connect(self.adjust_volume)
        pane.surface.activated.connect(lambda selected=pane: self.set_active_pane(selected))
        pane.play_button.clicked.connect(
            lambda checked=False, selected=pane: self.toggle_pane(selected)
        )
        pane.close_button.clicked.connect(
            lambda checked=False, selected=pane: self.close_pane(selected)
        )
        self.panes.append(pane)
        return pane

    # ---------- UI ----------

    def _build_ui(self) -> None:
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self.video_area = MediaDropArea()
        self.video_area.files_dropped.connect(
            lambda paths: self.add_dropped_paths(paths)
        )
        self.video_grid = QGridLayout(self.video_area)
        self.video_grid.setContentsMargins(0, 0, 0, 0)
        self.video_grid.setSpacing(3)
        central_layout.addWidget(self.video_area, 1)
        self._relayout_panes()
        self.set_active_pane(self.active_pane)

        self.controls = QWidget()
        controls_layout = QVBoxLayout(self.controls)
        controls_layout.setContentsMargins(12, 7, 12, 9)
        timeline = QHBoxLayout()
        self.time_label = QLabel("0:00")
        self.position_slider = InteractiveSlider(
            Qt.Orientation.Horizontal, self._format_position_hover
        )
        self.position_slider.setRange(0, 1000)
        self.position_slider.setToolTip(
            "Click or drag to seek; hover to preview the exact time"
        )
        self.position_slider.interaction_started.connect(self._position_pressed)
        self.position_slider.value_selected.connect(self._seek_to_slider_value)
        self.position_slider.interaction_finished.connect(self._position_released)
        self.duration_label = QLabel("0:00")
        timeline.addWidget(self.time_label)
        timeline.addWidget(self.position_slider, 1)
        timeline.addWidget(self.duration_label)
        controls_layout.addLayout(timeline)

        buttons = QHBoxLayout()
        self.previous_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaSkipBackward, self.previous_item, "Previous"
        )
        self.seek_backward_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaSeekBackward,
            self.skip_backward,
            "",
        )
        self.play_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaPlay, self.toggle_play, "Play / pause"
        )
        self.stop_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaStop, self.stop, "Stop"
        )
        self.next_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaSkipForward, self.next_item, "Next"
        )
        self.seek_forward_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaSeekForward,
            self.skip_forward,
            "",
        )
        self._refresh_skip_controls()
        self.frame_button = QPushButton("Frame")
        self.frame_button.setToolTip("Advance one frame")
        self.frame_button.clicked.connect(self.next_frame)
        self.speed = QComboBox()
        for rate in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0):
            self.speed.addItem(f"{rate:g}×", rate)
        self.speed.setCurrentText("1×")
        self.speed.currentIndexChanged.connect(
            lambda: self.player.set_rate(float(self.speed.currentData()))
        )
        self.volume_label = QLabel("Volume")
        self.volume_slider = InteractiveSlider(
            Qt.Orientation.Horizontal, lambda value: f"Volume: {value}%"
        )
        self.volume_slider.setRange(0, 125)
        self.volume_slider.setValue(85)
        self.volume_slider.setFixedWidth(130)
        self.volume_slider.setToolTip(
            "Click or drag to set volume; hover to preview the exact level"
        )
        self.volume_slider.valueChanged.connect(
            lambda value: self.player.audio_set_volume(value)
        )
        self.sidebar_button = QPushButton("Sidebar")
        self.sidebar_button.setToolTip("Show or hide the playlist and media library")
        self.sidebar_button.clicked.connect(
            lambda: self.sidebar.setVisible(not self.sidebar.isVisible())
        )
        buttons.addWidget(self.previous_button)
        buttons.addWidget(self.seek_backward_button)
        buttons.addWidget(self.play_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.seek_forward_button)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.frame_button)
        buttons.addSpacing(12)
        buttons.addWidget(QLabel("Speed"))
        buttons.addWidget(self.speed)
        buttons.addStretch(1)
        buttons.addWidget(self.volume_label)
        buttons.addWidget(self.volume_slider)
        buttons.addSpacing(8)
        buttons.addWidget(self.sidebar_button)
        controls_layout.addLayout(buttons)
        central_layout.addWidget(self.controls)
        self.setCentralWidget(central)

        self.sidebar = QDockWidget("Media", self)
        self.sidebar.setObjectName("mediaDock")
        self.sidebar.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.tabs = FullWidthTabWidget()
        self.playlist = QListWidget()
        self.playlist.setIconSize(THUMBNAIL_SIZE)
        self.playlist.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.playlist.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.playlist.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.playlist.setUniformItemSizes(True)
        self.playlist.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist.customContextMenuRequested.connect(self._playlist_context_menu)
        self.playlist.itemDoubleClicked.connect(self._playlist_double_clicked)
        playlist_page = QWidget()
        playlist_layout = QVBoxLayout(playlist_page)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        playlist_layout.addWidget(self.playlist, 1)
        self.shuffle_playlist_button = QPushButton("Shuffle playlist")
        self.shuffle_playlist_button.setToolTip(
            "Randomize the current playlist without interrupting playback"
        )
        self.shuffle_playlist_button.clicked.connect(self.shuffle_playlist)
        playlist_layout.addWidget(self.shuffle_playlist_button)
        self.tabs.addTab(playlist_page, "Playlist")

        library_page = QWidget()
        library_layout = QVBoxLayout(library_page)
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Search library…")
        self.library_search.textChanged.connect(self.refresh_library)
        self.library_tree = QTreeWidget()
        self.library_tree.setIconSize(THUMBNAIL_SIZE)
        self.library_tree.setHeaderLabels(["Title", "Type"])
        self.library_tree.setAlternatingRowColors(True)
        self.library_tree.setUniformRowHeights(False)
        self.library_tree.setAllColumnsShowFocus(True)
        self.library_tree.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.library_tree.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.library_tree.header().setStretchLastSection(False)
        self.library_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.library_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.library_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.library_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library_tree.customContextMenuRequested.connect(
            self._library_context_menu
        )
        self.library_tree.itemDoubleClicked.connect(self._library_double_clicked)
        delete_library_items = QAction(self.library_tree)
        delete_library_items.setShortcut("Delete")
        delete_library_items.triggered.connect(self.remove_library_selection)
        self.library_tree.addAction(delete_library_items)
        library_buttons = QHBoxLayout()
        add_folder = QPushButton("Add…")
        add_folder.setToolTip("Add a folder to the media library")
        add_folder.clicked.connect(self.add_library_folder)
        remove_library = QPushButton("Remove")
        remove_library.setToolTip(
            "Remove selected files or folders from the library (files stay on disk)"
        )
        remove_library.clicked.connect(self.remove_library_selection)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_library)
        self.shuffle_library_button = QPushButton("Shuffle")
        self.shuffle_library_button.setToolTip(
            "Queue every library item in random order and start the first one"
        )
        self.shuffle_library_button.clicked.connect(self.shuffle_library)
        library_buttons.addWidget(add_folder, 1)
        library_buttons.addWidget(remove_library, 1)
        library_buttons.addWidget(refresh, 1)
        library_buttons.addWidget(self.shuffle_library_button, 1)
        library_layout.addWidget(self.library_search)
        library_layout.addWidget(self.library_tree, 1)
        library_layout.addLayout(library_buttons)
        self.tabs.addTab(library_page, "Library")
        self.sidebar.setWidget(self.tabs)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)
        self.refresh_library()
        self.statusBar().showMessage("Ready")

    def _relayout_panes(self) -> None:
        for pane in self.panes:
            self.video_grid.removeWidget(pane.container)
            pane.container.hide()
        for index in range(3):
            self.video_grid.setRowStretch(index, 0)
            self.video_grid.setColumnStretch(index, 0)
        visible_panes = [pane for pane in self.panes if pane.path is not None]
        if not visible_panes:
            return
        positions = {
            1: [(0, 0, 1, 1)],
            2: [(0, 0, 1, 1), (0, 1, 1, 1)],
            3: [(0, 0, 1, 1), (1, 0, 1, 1), (2, 0, 1, 1)],
            4: [
                (0, 0, 1, 1),
                (0, 1, 1, 1),
                (1, 0, 1, 1),
                (1, 1, 1, 1),
            ],
        }
        for pane, position in zip(visible_panes, positions[len(visible_panes)]):
            self.video_grid.addWidget(pane.container, *position)
            pane.container.show()
        active_rows = {1: 1, 2: 1, 3: 3, 4: 2}[len(visible_panes)]
        active_columns = {1: 1, 2: 2, 3: 1, 4: 2}[len(visible_panes)]
        for index in range(active_rows):
            self.video_grid.setRowStretch(index, 1)
        for index in range(active_columns):
            self.video_grid.setColumnStretch(index, 1)

    def set_active_pane(self, pane: MediaPane) -> None:
        if pane not in self.panes:
            return
        self.active_pane = pane
        visible_count = sum(candidate.path is not None for candidate in self.panes)
        for candidate in self.panes:
            if self._fullscreen:
                border = "none"
                radius = 0
                candidate.header.hide()
                candidate.container.layout().setContentsMargins(0, 0, 0, 0)
                candidate.container.layout().setSpacing(0)
            elif visible_count <= 1:
                border = "none"
                radius = 6
            elif candidate is pane:
                border = "1px solid #e2e6ed"
                radius = 6
            else:
                border = "1px solid #343638"
                radius = 6
            candidate.container.setStyleSheet(
                "QWidget#mediaPane {"
                f"border: {border}; border-radius: {radius}px; background: #0b0c0d;"
                "}"
            )
            candidate.surface.setStyleSheet("background: #000; border: 0;")
        if pane.path is not None:
            self._attach_video_output(pane)
        if hasattr(self, "volume_slider"):
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(max(0, pane.player.audio_get_volume()))
            self.volume_slider.blockSignals(False)
        title = Path(pane.path).name if pane.path else "Aurora Player"
        self.setWindowTitle(f"{title} — Aurora Player" if pane.path else title)

    def _left_mouse_pressed(self) -> bool:
        if sys.platform == "win32":
            try:
                return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
            except (AttributeError, OSError):
                pass
        return bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)

    def _select_pane_at_global_position(self, position) -> bool:
        visible_panes = [
            pane
            for pane in self.panes
            if pane.path is not None and pane.surface.isVisible()
        ]
        if len(visible_panes) < 2:
            return False
        for pane in visible_panes:
            local_position = pane.surface.mapFromGlobal(position)
            if pane.surface.rect().contains(local_position):
                self.set_active_pane(pane)
                return True
        return False

    def _poll_pane_selection(self) -> None:
        mouse_down = self._left_mouse_pressed()
        if mouse_down and not self._pane_mouse_was_down:
            self._select_pane_at_global_position(QCursor.pos())
        self._pane_mouse_was_down = mouse_down

    def _pane_at_global_position(self, position) -> MediaPane | None:
        for pane in self.panes:
            if pane.path is None or not pane.container.isVisible():
                continue
            local_position = pane.container.mapFromGlobal(position)
            if pane.container.rect().contains(local_position):
                return pane
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if not paths:
            super().dropEvent(event)
            return
        position = self.mapToGlobal(event.position().toPoint())
        target = self._pane_at_global_position(position)
        self.add_dropped_paths(paths, target)
        event.acceptProposedAction()

    def add_pane(self, path: str | None = None) -> MediaPane | None:
        if path is None:
            self.choose_files()
            return None
        empty_pane = next((pane for pane in self.panes if pane.path is None), None)
        if empty_pane is not None:
            self.open_media(path, empty_pane)
            return empty_pane
        if len(self.panes) >= 4:
            self.statusBar().showMessage(
                "Four videos are already open. Select a pane to replace it.", 5000
            )
            return None
        pane = self._create_pane()
        self.open_media(path, pane)
        return pane

    def close_active_pane(self) -> None:
        if self._cleanup_started:
            return
        pane = self.active_pane
        self._save_resume_position(pane, force=True)
        player = pane.player
        self._quiesce_pane(pane)
        if len(self.panes) == 1:
            pane.player = pane.instance.media_player_new()
            pane.path = None
            pane.end_advanced = False
            pane.last_resume_write = 0.0
            pane.title_label.setText("Empty video pane")
            pane.title_label.setToolTip("Click the video to select this pane")
            pane.surface.update()
            self.timer.stop()
            self.time_label.setText("0:00")
            self.duration_label.setText("0:00")
            self.position_slider.setValue(0)
            self._relayout_panes()
            self.set_active_pane(pane)
            self._vlc_cleanup.release_player(player)
            return
        index = self.panes.index(pane)
        self.panes.remove(pane)
        self.video_grid.removeWidget(pane.container)
        pane.container.hide()
        self._relayout_panes()
        self.set_active_pane(self.panes[min(index, len(self.panes) - 1)])
        self._vlc_cleanup.release_player(
            player,
            lambda container=pane.container: (
                self.pane_cleanup_finished.emit(container)
            ),
        )

    def _quiesce_pane(self, pane: MediaPane) -> None:
        """Silence and detach a pane before native cleanup is queued."""
        try:
            pane.player.audio_set_mute(True)
        except Exception:
            pass
        try:
            if pane.player.is_playing():
                pane.player.set_pause(1)
        except Exception:
            pass
        try:
            if sys.platform == "win32":
                pane.player.set_hwnd(0)
            elif sys.platform.startswith("linux"):
                pane.player.set_xwindow(0)
            elif sys.platform == "darwin":
                pane.player.set_nsobject(0)
        except Exception:
            pass

    def _finalize_closed_pane(self, container: QWidget) -> None:
        self._completed_pane_cleanups += 1
        container.deleteLater()

    def close_pane(self, pane: MediaPane) -> None:
        self.set_active_pane(pane)
        self.close_active_pane()

    def toggle_pane(self, pane: MediaPane) -> None:
        self.set_active_pane(pane)
        if pane.player.is_playing():
            pane.player.pause()
        elif pane.path:
            pane.player.play()

    def _tool_button(self, icon, callback, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        return button

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self._action(
            file_menu, "Open file(s)…", self.choose_files, shortcut_id="open_files"
        )
        self._action(
            file_menu, "Open folder…", self.choose_folder, shortcut_id="open_folder"
        )
        self._action(
            file_menu, "Open disc…", self.open_disc, shortcut_id="open_disc"
        )
        self._action(
            file_menu, "Open network URL…", self.open_url, shortcut_id="open_url"
        )
        self._action(file_menu, "Load external subtitle…", self.load_subtitle)
        file_menu.addSeparator()
        self._action(
            file_menu, "Add video pane", self.choose_files, shortcut_id="add_pane"
        )
        self._action(
            file_menu,
            "Convert / transcode…",
            self.show_converter,
            shortcut_id="convert",
        )
        file_menu.addSeparator()
        self._action(
            file_menu,
            "Save playlist…",
            self.save_playlist,
            shortcut_id="save_playlist",
        )
        self._action(file_menu, "Load playlist…", self.load_playlist)
        file_menu.addSeparator()
        self._action(
            file_menu, "Close window", self.close, shortcut_id="close_window"
        )

        playback = self.menuBar().addMenu("&Playback")
        self._action(
            playback, "Play / pause", self.toggle_play, shortcut_id="play_pause"
        )
        self._action(
            playback,
            "Play / pause all panes",
            self.toggle_all,
            shortcut_id="play_pause_all",
        )
        self._action(playback, "Stop", self.stop, shortcut_id="stop")
        self._action(
            playback, "Next frame", self.next_frame, shortcut_id="next_frame"
        )
        playback.addSeparator()
        self._action(
            playback,
            "Shuffle playlist",
            self.shuffle_playlist,
            shortcut_id="shuffle_playlist",
        )
        self._action(
            playback,
            "Shuffle library",
            self.shuffle_library,
            shortcut_id="shuffle_library",
        )
        playback.addSeparator()
        self._action(
            playback, "Set A point", self.set_a_point, shortcut_id="set_a"
        )
        self._action(
            playback, "Set B point", self.set_b_point, shortcut_id="set_b"
        )
        self._action(
            playback,
            "Clear A–B loop",
            self.clear_ab_loop,
            shortcut_id="clear_ab",
        )
        self._action(playback, "Synchronize audio/subtitles…", self.show_sync)
        playback.addSeparator()
        resume_action = self._action(
            playback, "Resume playback automatically", self.set_resume_enabled
        )
        resume_action.setCheckable(True)
        resume_action.setChecked(
            str(self.settings.value("playback/resume_enabled", "true")).lower()
            == "true"
        )
        self._action(
            playback, "Clear saved playback positions…", self.clear_resume_history
        )

        self.audio_menu = self.menuBar().addMenu("&Audio")
        self.audio_tracks_menu = self.audio_menu.addMenu("Audio track")
        self._action(self.audio_menu, "Audio effects…", self.show_audio_effects)
        self.audio_menu.aboutToShow.connect(self._refresh_audio_tracks)

        subtitle = self.menuBar().addMenu("&Subtitles")
        self.subtitle_tracks_menu = subtitle.addMenu("Subtitle track")
        self._action(subtitle, "Load subtitle file…", self.load_subtitle)
        self._action(subtitle, "Appearance…", self.show_subtitle_style)
        subtitle.aboutToShow.connect(self._refresh_subtitle_tracks)

        video_menu = self.menuBar().addMenu("&Video")
        self.video_tracks_menu = video_menu.addMenu("Video track")
        aspect_menu = video_menu.addMenu("Aspect ratio")
        for label, ratio in [
            ("Default", None),
            ("16:9", "16:9"),
            ("16:10", "16:10"),
            ("4:3", "4:3"),
            ("1:1", "1:1"),
            ("2.35:1", "2.35:1"),
        ]:
            self._action(
                aspect_menu,
                label,
                lambda checked=False, value=ratio: self.set_aspect_ratio(value),
            )
        crop_menu = video_menu.addMenu("Crop")
        for label, crop in [
            ("None", None),
            ("16:9", "16:9"),
            ("4:3", "4:3"),
            ("1:1", "1:1"),
        ]:
            self._action(
                crop_menu,
                label,
                lambda checked=False, value=crop: self.set_crop(value),
            )
        zoom_menu = video_menu.addMenu("Zoom")
        for label, scale in [
            ("Fit", 0.0),
            ("50%", 0.5),
            ("100%", 1.0),
            ("150%", 1.5),
            ("200%", 2.0),
        ]:
            self._action(
                zoom_menu,
                label,
                lambda checked=False, value=scale: self.player.video_set_scale(value),
            )
        self._action(video_menu, "Video effects…", self.show_video_effects)
        self._action(
            video_menu,
            "Close active pane",
            self.close_active_pane,
            shortcut_id="close_pane",
        )
        self._action(
            video_menu,
            "Fullscreen",
            self.toggle_fullscreen,
            shortcut_id="fullscreen",
        )
        video_menu.aboutToShow.connect(self._refresh_video_tracks)

        view_menu = self.menuBar().addMenu("&View")
        sidebar_action = self.sidebar.toggleViewAction()
        sidebar_action.setText("Show / hide sidebar")
        self._register_shortcut_action("toggle_sidebar", sidebar_action)
        view_menu.addAction(sidebar_action)
        skins = view_menu.addMenu("Skin")
        theme_group = QActionGroup(skins)
        theme_group.setExclusive(True)
        selected_theme = str(self.settings.value("appearance/skin", "dark"))
        for theme_name, palette in self.application_controller.themes.items():
            action = self._action(
                skins,
                str(palette["label"]),
                lambda checked=False, name=theme_name: (
                    self.application_controller.apply_skin(name)
                ),
            )
            action.setCheckable(True)
            action.setChecked(theme_name == selected_theme)
            theme_group.addAction(action)
        skins.addSeparator()
        self._action(skins, "Import QSS skin…", self.import_skin)
        view_menu.addSeparator()
        self._action(
            view_menu, "Customize keyboard shortcuts…", self.show_shortcut_editor
        )

        settings_menu = self.menuBar().addMenu("&Settings")
        skip_menu = settings_menu.addMenu("Playback skip amount")
        self.skip_interval_group = QActionGroup(skip_menu)
        self.skip_interval_group.setExclusive(True)
        for seconds in SKIP_SECONDS_OPTIONS:
            action = self._action(
                skip_menu,
                f"{seconds} seconds",
                lambda checked=False, value=seconds: self.set_skip_seconds(value),
            )
            action.setCheckable(True)
            action.setData(seconds)
            action.setChecked(seconds == self._skip_seconds)
            self.skip_interval_group.addAction(action)

        help_menu = self.menuBar().addMenu("&Help")
        self._action(help_menu, "Keyboard and mouse controls", self.show_controls)
        self._action(
            help_menu,
            "Check for updates…",
            lambda: self.application_controller.check_for_updates(manual=True),
        )
        automatic_updates = self._action(
            help_menu,
            "Check for updates automatically",
            self.application_controller.set_automatic_updates,
        )
        automatic_updates.setCheckable(True)
        automatic_updates.setChecked(
            str(self.settings.value("updates/automatic", "true")).lower() == "true"
        )
        help_menu.addSeparator()
        self._action(help_menu, "About Aurora Player", self.show_about)

    def _bind_shortcuts(self) -> None:
        shortcuts = {
            "seek_back_5": self.skip_backward,
            "seek_forward_5": self.skip_forward,
            "seek_back_30": lambda: self.seek_relative(-30000),
            "seek_forward_30": lambda: self.seek_relative(30000),
            "volume_up": lambda: self.adjust_volume(5),
            "volume_down": lambda: self.adjust_volume(-5),
            "mute": self.toggle_mute,
            "fullscreen_alternate": self.toggle_fullscreen,
            "leave_fullscreen": self.leave_fullscreen,
        }
        for shortcut_id, callback in shortcuts.items():
            action = QAction(self)
            action.triggered.connect(callback)
            self.addAction(action)
            self._register_shortcut_action(shortcut_id, action)

    def _shortcut_value(self, shortcut_id: str) -> str:
        default = SHORTCUT_DEFINITIONS[shortcut_id][1]
        return str(self.settings.value(f"shortcuts/{shortcut_id}", default))

    def _register_shortcut_action(
        self, shortcut_id: str, action: QAction
    ) -> QAction:
        action.setShortcut(QKeySequence(self._shortcut_value(shortcut_id)))
        self.shortcut_actions[shortcut_id] = action
        return action

    def _action(
        self,
        menu: QMenu,
        text: str,
        callback,
        shortcut: str | None = None,
        shortcut_id: str | None = None,
    ) -> QAction:
        action = QAction(text, self)
        if shortcut_id:
            self._register_shortcut_action(shortcut_id, action)
        elif shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def _attach_video_output(self, pane: MediaPane | None = None) -> None:
        pane = pane or self.active_pane
        window_id = int(pane.surface.winId())
        if sys.platform == "win32":
            pane.player.set_hwnd(window_id)
        elif sys.platform.startswith("linux"):
            pane.player.set_xwindow(window_id)
        elif sys.platform == "darwin":
            pane.player.set_nsobject(window_id)

    # ---------- opening and playlists ----------

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open media",
            "",
            "Media files (*.*)",
        )
        if paths:
            self.add_files(paths)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open media folder")
        if folder:
            self.add_files(expand_media_paths([folder]))

    def add_dropped_paths(
        self, paths: Iterable[str], target_pane: MediaPane | None = None
    ) -> None:
        expanded = expand_media_paths(paths)
        if not expanded:
            self.statusBar().showMessage(
                "No supported media files were found in the dropped items.", 5000
            )
            return
        self.add_files(expanded, preferred_pane=target_pane)

    def add_files(
        self,
        paths: Iterable[str],
        preferred_pane: MediaPane | None = None,
    ) -> None:
        first_new_index = self.playlist.count()
        valid: list[str] = []
        for raw_path in paths:
            path = str(Path(raw_path).expanduser().resolve())
            if not Path(path).is_file():
                continue
            self._append_playlist_item(path)
            valid.append(path)
        if valid:
            self.library.add_paths(valid)
            self.refresh_library()
            self.playlist.setCurrentRow(first_new_index)
            pending = list(valid)
            if preferred_pane in self.panes and pending:
                self.open_media(pending.pop(0), preferred_pane)
            queued = 0
            for path in pending:
                target = next(
                    (pane for pane in self.panes if pane.path is None), None
                )
                if target is None and len(self.panes) < 4:
                    target = self._create_pane()
                if target is not None:
                    self.open_media(path, target)
                else:
                    queued += 1
            if queued:
                self.statusBar().showMessage(
                    f"Four-pane limit reached; {queued} item(s) added to the playlist.",
                    6000,
                )

    def open_media(
        self, location: str, pane: MediaPane | None = None
    ) -> None:
        pane = pane or self.active_pane
        self._save_resume_position(pane, force=True)
        pane.path = location
        pane.last_resume_write = time.monotonic()
        self._relayout_panes()
        self.set_active_pane(pane)
        media = pane.instance.media_new(location)
        self._apply_media_options(media)
        pane.player.set_media(media)
        pane.end_advanced = False
        self._attach_video_output(pane)
        pane.player.audio_set_volume(self.volume_slider.value())
        pane.player.play()
        if not self.timer.isActive():
            self.timer.start()
        pane.title_label.setText(Path(location).name or location)
        pane.title_label.setToolTip(location)
        self.set_active_pane(pane)
        self.statusBar().showMessage(location)
        QTimer.singleShot(
            350, lambda target=pane: self._apply_live_settings(target)
        )
        QTimer.singleShot(
            700,
            lambda target=pane, expected=location: self._resume_media(
                target, expected
            ),
        )

    def _resume_enabled(self) -> bool:
        return (
            str(self.settings.value("playback/resume_enabled", "true")).lower()
            == "true"
        )

    def set_resume_enabled(self, enabled: bool) -> None:
        self.settings.setValue("playback/resume_enabled", enabled)
        self.statusBar().showMessage(
            "Playback resume enabled." if enabled else "Playback resume disabled.",
            3000,
        )

    def _resume_media(self, pane: MediaPane, expected_location: str) -> None:
        if (
            self._cleanup_started
            or not self._resume_enabled()
            or pane not in self.panes
            or pane.path != expected_location
            or "://" in expected_location
        ):
            return
        saved = self.library.playback_position(expected_location)
        if saved is None:
            return
        position_ms, saved_duration_ms = saved
        duration_ms = max(0, pane.player.get_length(), saved_duration_ms)
        if position_ms < 10_000 or (
            duration_ms > 0 and position_ms >= duration_ms - 15_000
        ):
            self.library.clear_playback_position(expected_location)
            return
        pane.player.set_time(position_ms)
        if pane is self.active_pane:
            self.statusBar().showMessage(
                f"Resumed at {format_time(position_ms)}", 5000
            )

    def _save_resume_position(
        self, pane: MediaPane, force: bool = False
    ) -> None:
        if (
            not self._resume_enabled()
            or not pane.path
            or "://" in pane.path
        ):
            return
        now = time.monotonic()
        if not force and now - pane.last_resume_write < 5.0:
            return
        position_ms = pane.player.get_time()
        duration_ms = pane.player.get_length()
        if position_ms >= 0:
            self.library.save_playback_position(
                pane.path, position_ms, duration_ms
            )
            pane.last_resume_write = now

    def clear_resume_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear saved playback positions",
            "Forget every saved resume position?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.library.clear_playback_positions()
            self.statusBar().showMessage(
                "Saved playback positions cleared.", 3000
            )

    def _apply_media_options(self, media: vlc.Media) -> None:
        size = int(self.settings.value("subtitles/font_size", 24))
        margin = int(self.settings.value("subtitles/margin", 30))
        position = str(self.settings.value("subtitles/position", "Bottom"))
        bold = str(self.settings.value("subtitles/bold", "false")).lower() == "true"
        media.add_option(f":freetype-fontsize={size}")
        media.add_option(f":freetype-bold={int(bold)}")
        # VLC renders subtitles upward from the bottom using sub-margin. These
        # presets provide useful starting offsets; the margin setting fine-tunes
        # the result for a particular video resolution.
        vertical_offsets = {"Bottom": 0, "Center": 300, "Top": 600}
        media.add_option(
            f":sub-margin={margin + vertical_offsets.get(position, 0)}"
        )
        media.add_option(":sub-align=0")
        filters = []
        compressor, spatializer = self._audio_filters
        if compressor:
            filters.append("compressor")
        if spatializer:
            filters.append("spatializer")
        if filters:
            media.add_option(f":audio-filter={','.join(filters)}")
        video_filters: list[str] = []
        if self._sharpen > 0:
            video_filters.append("sharpen")
            media.add_option(f":sharpen-sigma={self._sharpen:.2f}")
        if video_filters:
            # Hardware-decoded surfaces can bypass VLC's sharpen filter on
            # Windows. Disable hardware decoding only while it is requested.
            media.add_option(":avcodec-hw=none")
            media.add_option(f":video-filter={':'.join(video_filters)}")

    def _apply_live_settings(self, pane: MediaPane | None = None) -> None:
        pane = pane or self.active_pane
        if self._cleanup_started or pane not in self.panes:
            return
        pane.player.audio_set_delay(self._audio_delay_ms * 1000)
        pane.player.video_set_spu_delay(self._subtitle_delay_ms * 1000)
        pane.player.set_rate(float(self.speed.currentData()))

    def reload_current(self) -> None:
        if not self.current_path:
            return
        pane = self.active_pane
        position = pane.player.get_time()
        pane.player.stop()
        self.open_media(self.current_path, pane)
        QTimer.singleShot(500, lambda: pane.player.set_time(position))

    def new_window(self) -> None:
        self.choose_files()

    def open_in_available_pane(self, location: str) -> None:
        empty_pane = next((pane for pane in self.panes if pane.path is None), None)
        if empty_pane is not None:
            self.open_media(location, empty_pane)
        elif len(self.panes) < 4:
            pane = self._create_pane()
            self.open_media(location, pane)
        else:
            self.open_media(location, self.active_pane)

    def open_disc(self) -> None:
        dialog = DiscDialog(self)
        if dialog.exec():
            self.open_in_available_pane(dialog.media_location())

    def open_url(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        url, ok = QInputDialog.getText(self, "Open URL", "Network media URL")
        if ok and url.strip():
            self.open_in_available_pane(url.strip())

    def load_subtitle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load subtitle",
            "",
            "Subtitle files (*.srt *.ass *.ssa *.vtt *.sub *.idx);;All files (*.*)",
        )
        if path and self.player.video_set_subtitle_file(path) != 0:
            QMessageBox.warning(self, "Subtitle", "VLC could not load that subtitle.")

    def save_playlist(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save playlist", "playlist.m3u8", "M3U playlists (*.m3u8 *.m3u)"
        )
        if path:
            save_m3u(path, self.playlist_paths())

    def load_playlist(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load playlist", "", "M3U playlists (*.m3u8 *.m3u)"
        )
        if path:
            self.add_files(load_m3u(path))

    def playlist_paths(self) -> list[str]:
        return [
            str(self.playlist.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.playlist.count())
        ]

    def _append_playlist_item(self, path: str) -> QListWidgetItem:
        item = QListWidgetItem(
            QIcon(QPixmap.fromImage(media_placeholder(path))), Path(path).name
        )
        item.setSizeHint(QSize(0, THUMBNAIL_SIZE.height() + 8))
        item.setToolTip(path)
        item.setData(Qt.ItemDataRole.UserRole, path)
        self.playlist.addItem(item)
        self.thumbnail_provider.request(path)
        return item

    def _apply_thumbnail(self, path: str, image: QImage) -> None:
        icon = QIcon(QPixmap.fromImage(image))
        for index in range(self.playlist.count()):
            item = self.playlist.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole)) == path:
                item.setIcon(icon)
        pending = [
            self.library_tree.topLevelItem(index)
            for index in range(self.library_tree.topLevelItemCount())
        ]
        while pending:
            item = pending.pop()
            if str(item.data(0, Qt.ItemDataRole.UserRole)) == path:
                item.setIcon(0, icon)
            pending.extend(item.child(index) for index in range(item.childCount()))

    def shuffle_playlist(self) -> None:
        if self.playlist.count() < 2:
            self.statusBar().showMessage(
                "Add at least two items to shuffle the playlist.", 3500
            )
            return
        current = self.playlist.currentItem()
        items = [self.playlist.takeItem(0) for _ in range(self.playlist.count())]
        original_order = list(items)
        random.shuffle(items)
        if items == original_order:
            items.append(items.pop(0))
        for item in items:
            self.playlist.addItem(item)
        if current is not None:
            self.playlist.setCurrentItem(current)
        self.statusBar().showMessage(f"Shuffled {len(items)} playlist items.", 3500)

    def shuffle_library(self) -> None:
        paths = [
            media.path
            for media in self.library.items()
            if Path(media.path).is_file()
        ]
        if not paths:
            self.statusBar().showMessage("The media library is empty.", 3500)
            return
        random.shuffle(paths)
        self.playlist.clear()
        for path in paths:
            self._append_playlist_item(path)
        self.playlist.setCurrentRow(0)
        self.open_media(paths[0])
        self.statusBar().showMessage(
            f"Shuffled {len(paths)} library items into the playlist.", 5000
        )

    def _playlist_double_clicked(self, item: QListWidgetItem) -> None:
        self.open_in_available_pane(str(item.data(Qt.ItemDataRole.UserRole)))

    def _playlist_context_menu(self, point) -> None:
        item = self.playlist.itemAt(point)
        if not item:
            return
        menu = QMenu(self)
        play = menu.addAction("Play in active pane")
        new_pane = menu.addAction("Open in new pane")
        new_pane.setEnabled(len(self.panes) < 4)
        shuffle = menu.addAction("Shuffle playlist")
        remove = menu.addAction("Remove from playlist")
        selected = menu.exec(self.playlist.mapToGlobal(point))
        if selected == play:
            self.open_media(str(item.data(Qt.ItemDataRole.UserRole)))
        elif selected == new_pane:
            self.add_pane(str(item.data(Qt.ItemDataRole.UserRole)))
        elif selected == shuffle:
            self.shuffle_playlist()
        elif selected == remove:
            self.playlist.takeItem(self.playlist.row(item))

    # ---------- library ----------

    def add_library_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add folder to library")
        if not folder:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            count = self.library.scan_folder(folder)
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh_library()
        self.statusBar().showMessage(f"Added or updated {count} media files", 5000)

    def refresh_library(self) -> None:
        self.library_tree.clear()
        kind_role = int(Qt.ItemDataRole.UserRole) + 1
        media_items = self.library.items(self.library_search.text())
        folder_roots = [Path(path) for path in self.library.folders()]
        grouped = {root: [] for root in folder_roots}
        loose_items = []
        for media in media_items:
            media_path = Path(media.path)
            matching_roots = [
                root for root in folder_roots if media_path.is_relative_to(root)
            ]
            if matching_roots:
                grouped[max(matching_roots, key=lambda root: len(root.parts))].append(
                    media
                )
            else:
                loose_items.append(media)

        for root in folder_roots:
            children = grouped[root]
            if not children and self.library_search.text().strip():
                continue
            folder_name = root.name or str(root)
            folder_item = QTreeWidgetItem(
                [folder_name, f"Folder ({len(children)})"]
            )
            folder_item.setData(0, Qt.ItemDataRole.UserRole, str(root))
            folder_item.setData(0, kind_role, "folder")
            folder_item.setToolTip(0, str(root))
            folder_item.setIcon(
                0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            )
            self.library_tree.addTopLevelItem(folder_item)
            for media in children:
                item = QTreeWidgetItem([media.title, media.kind])
                item.setData(0, Qt.ItemDataRole.UserRole, media.path)
                item.setData(0, kind_role, "media")
                item.setToolTip(0, media.path)
                item.setIcon(
                    0, QIcon(QPixmap.fromImage(media_placeholder(media.path)))
                )
                item.setSizeHint(0, QSize(0, THUMBNAIL_SIZE.height() + 8))
                folder_item.addChild(item)
                self.thumbnail_provider.request(media.path)
            folder_item.setExpanded(True)

        for media in loose_items:
            item = QTreeWidgetItem([media.title, media.kind])
            item.setData(0, Qt.ItemDataRole.UserRole, media.path)
            item.setData(0, kind_role, "media")
            item.setToolTip(0, media.path)
            item.setIcon(
                0, QIcon(QPixmap.fromImage(media_placeholder(media.path)))
            )
            item.setSizeHint(0, QSize(0, THUMBNAIL_SIZE.height() + 8))
            self.library_tree.addTopLevelItem(item)
            self.thumbnail_provider.request(media.path)

    def _library_double_clicked(self, item: QTreeWidgetItem) -> None:
        kind_role = int(Qt.ItemDataRole.UserRole) + 1
        if item.data(0, kind_role) != "media":
            item.setExpanded(not item.isExpanded())
            return
        path = str(item.data(0, Qt.ItemDataRole.UserRole))
        self.add_files([path])

    def _library_context_menu(self, point) -> None:
        item = self.library_tree.itemAt(point)
        if item is None:
            return
        if not item.isSelected():
            self.library_tree.clearSelection()
            item.setSelected(True)
        selected_items = self.library_tree.selectedItems()
        kind_role = int(Qt.ItemDataRole.UserRole) + 1
        folders = sum(item.data(0, kind_role) == "folder" for item in selected_items)
        files = sum(item.data(0, kind_role) == "media" for item in selected_items)
        if not folders and not files:
            return
        if folders and files:
            label = "Remove selected items from library"
        elif folders:
            label = "Remove folder from library" if folders == 1 else "Remove folders from library"
        else:
            label = "Remove file from library" if files == 1 else "Remove files from library"
        menu = QMenu(self)
        shuffle_action = menu.addAction("Shuffle library")
        remove_action = menu.addAction(label)
        selected = menu.exec(self.library_tree.mapToGlobal(point))
        if selected == shuffle_action:
            self.shuffle_library()
        elif selected == remove_action:
            self.remove_library_selection()

    def remove_library_selection(self) -> None:
        selected_items = self.library_tree.selectedItems()
        if not selected_items:
            self.statusBar().showMessage(
                "Select a library file or folder to remove.", 3500
            )
            return
        kind_role = int(Qt.ItemDataRole.UserRole) + 1
        folders = {
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in selected_items
            if item.data(0, kind_role) == "folder"
        }
        paths = {
            str(item.data(0, Qt.ItemDataRole.UserRole))
            for item in selected_items
            if item.data(0, kind_role) == "media"
        }
        for folder in folders:
            root = Path(folder)
            paths = {path for path in paths if not Path(path).is_relative_to(root)}
        removed = sum(self.library.remove_folder(folder) for folder in folders)
        removed += self.library.remove_paths(paths)
        self.refresh_library()
        self.statusBar().showMessage(
            f"Removed {removed} media item(s) from the library. Files remain on disk.",
            6000,
        )

    # ---------- playback ----------

    def toggle_play(self) -> None:
        if self.player.is_playing():
            self.player.pause()
        elif self.current_path:
            self.player.play()
        elif self.playlist.count():
            self.playlist.setCurrentRow(0)
            self.open_media(self.playlist_paths()[0])

    def toggle_all(self) -> None:
        playing = any(pane.player.is_playing() for pane in self.panes)
        for pane in self.panes:
            if playing and pane.player.is_playing():
                pane.player.pause()
            elif not playing and pane.path:
                pane.player.play()

    def stop(self) -> None:
        self._save_resume_position(self.active_pane, force=True)
        self.player.stop()

    def next_frame(self) -> None:
        self.player.next_frame()

    def previous_item(self) -> None:
        if not self.playlist.count():
            return
        row = max(0, self.playlist.currentRow() - 1)
        self.playlist.setCurrentRow(row)
        self.open_media(self.playlist_paths()[row])

    def next_item(self) -> None:
        if not self.playlist.count():
            return
        row = self.playlist.currentRow()
        row = (row + 1) % self.playlist.count()
        self.playlist.setCurrentRow(row)
        self.open_media(self.playlist_paths()[row])

    def seek_relative(self, milliseconds: int) -> None:
        current = self.player.get_time()
        if current >= 0:
            self.player.set_time(max(0, current + milliseconds))

    def skip_backward(self) -> None:
        self.seek_relative(-self._skip_seconds * 1000)

    def skip_forward(self) -> None:
        self.seek_relative(self._skip_seconds * 1000)

    def _seek_from_gesture(self, milliseconds: int) -> None:
        if milliseconds:
            direction = 1 if milliseconds > 0 else -1
            self.seek_relative(self._skip_seconds * 1000 * direction)

    def set_skip_seconds(self, seconds: int) -> None:
        self._skip_seconds = set_playback_skip_seconds(self.settings, seconds)
        self._refresh_skip_controls()
        self.statusBar().showMessage(
            f"Playback skip amount set to {self._skip_seconds} seconds.",
            3000,
        )

    def _refresh_skip_controls(self) -> None:
        seconds = self._skip_seconds
        self.seek_backward_button.setText(f"{seconds}s")
        self.seek_backward_button.setToolTip(
            f"Skip backward {seconds} seconds"
        )
        self.seek_forward_button.setText(f"{seconds}s")
        self.seek_forward_button.setToolTip(
            f"Skip forward {seconds} seconds"
        )

    def adjust_volume(self, amount: int) -> None:
        self.volume_slider.setValue(self.volume_slider.value() + amount)

    def toggle_mute(self) -> None:
        self.player.audio_toggle_mute()

    def _position_pressed(self) -> None:
        self._slider_dragging = True

    def _format_position_hover(self, slider_value: int) -> str:
        duration = max(0, self.player.get_length())
        position = round(duration * slider_value / 1000)
        return f"{format_time(position)} / {format_time(duration)}"

    def _seek_to_slider_value(self, slider_value: int) -> None:
        self.player.set_position(slider_value / 1000.0)
        duration = max(0, self.player.get_length())
        if duration:
            self.time_label.setText(
                format_time(round(duration * slider_value / 1000))
            )

    def _position_released(self) -> None:
        self.player.set_position(self.position_slider.value() / 1000.0)
        self._slider_dragging = False

    def set_a_point(self) -> None:
        self._ab_start = max(0, self.player.get_time())
        self.statusBar().showMessage(f"A point: {format_time(self._ab_start)}", 3000)

    def set_b_point(self) -> None:
        value = max(0, self.player.get_time())
        if self._ab_start is None:
            QMessageBox.information(self, "A–B loop", "Set the A point first.")
            return
        if value <= self._ab_start:
            QMessageBox.information(self, "A–B loop", "The B point must be after A.")
            return
        self._ab_end = value
        self.statusBar().showMessage(
            f"Looping {format_time(self._ab_start)}–{format_time(self._ab_end)}",
            5000,
        )

    def clear_ab_loop(self) -> None:
        self._ab_start = None
        self._ab_end = None
        self.statusBar().showMessage("A–B loop cleared", 3000)

    def _update_playback(self) -> None:
        current = self.player.get_time()
        duration = self.player.get_length()
        if current >= 0:
            self.time_label.setText(format_time(current))
        if duration > 0:
            self.duration_label.setText(format_time(duration))
            if not self._slider_dragging:
                self.position_slider.setValue(int(max(0, self.player.get_position()) * 1000))
        icon = (
            QStyle.StandardPixmap.SP_MediaPause
            if self.player.is_playing()
            else QStyle.StandardPixmap.SP_MediaPlay
        )
        self.play_button.setIcon(self.style().standardIcon(icon))
        for pane in self.panes:
            self._save_resume_position(pane)
            pane_icon = (
                QStyle.StandardPixmap.SP_MediaPause
                if pane.player.is_playing()
                else QStyle.StandardPixmap.SP_MediaPlay
            )
            pane.play_button.setIcon(self.style().standardIcon(pane_icon))
            if pane.player.get_state() == vlc.State.Ended and pane.path:
                self.library.clear_playback_position(pane.path)
        if (
            self._ab_start is not None
            and self._ab_end is not None
            and current >= self._ab_end
        ):
            self.player.set_time(self._ab_start)
        if (
            self.player.get_state() == vlc.State.Ended
            and not self.active_pane.end_advanced
        ):
            self.active_pane.end_advanced = True
            if self.playlist.count() > 1:
                self.next_item()

    # ---------- tracks and effects ----------

    def _fill_track_menu(self, menu: QMenu, descriptions, setter, active: int) -> None:
        menu.clear()
        group = QActionGroup(menu)
        group.setExclusive(True)
        if not descriptions:
            empty = menu.addAction("No tracks available")
            empty.setEnabled(False)
            return
        for track_id, raw_name in descriptions:
            action = QAction(decode_label(raw_name), menu)
            action.setCheckable(True)
            action.setChecked(int(track_id) == active)
            action.triggered.connect(
                lambda checked=False, value=int(track_id): setter(value)
            )
            group.addAction(action)
            menu.addAction(action)

    def _refresh_audio_tracks(self) -> None:
        self._fill_track_menu(
            self.audio_tracks_menu,
            self.player.audio_get_track_description(),
            self.player.audio_set_track,
            self.player.audio_get_track(),
        )

    def _refresh_subtitle_tracks(self) -> None:
        self._fill_track_menu(
            self.subtitle_tracks_menu,
            self.player.video_get_spu_description(),
            self.player.video_set_spu,
            self.player.video_get_spu(),
        )

    def _refresh_video_tracks(self) -> None:
        self._fill_track_menu(
            self.video_tracks_menu,
            self.player.video_get_track_description(),
            self.player.video_set_track,
            self.player.video_get_track(),
        )

    def show_sync(self) -> None:
        dialog = SyncDialog(
            self._audio_delay_ms, self._subtitle_delay_ms, self
        )
        dialog.values_changed.connect(self.set_sync)
        dialog.show()
        self._keep_dialog(dialog)

    def set_sync(self, audio_ms: int, subtitle_ms: int) -> None:
        self._audio_delay_ms = audio_ms
        self._subtitle_delay_ms = subtitle_ms
        self._apply_live_settings()

    def show_subtitle_style(self) -> None:
        dialog = SubtitleStyleDialog(self.settings, self)
        dialog.style_changed.connect(lambda _: self.reload_current())
        dialog.show()
        self._keep_dialog(dialog)

    def show_video_effects(self) -> None:
        dialog = VideoEffectsDialog(self.player, self._sharpen, self)
        dialog.sharpen_changed.connect(self.set_sharpen)
        dialog.show()
        self._keep_dialog(dialog)

    def show_audio_effects(self) -> None:
        dialog = AudioEffectsDialog(self)
        dialog.equalizer_selected.connect(self.set_equalizer)
        dialog.filters_changed.connect(self.set_audio_filters)
        dialog.show()
        self._keep_dialog(dialog)

    def set_equalizer(self, equalizer) -> None:
        self._equalizer = equalizer
        self.player.audio_set_equalizer(equalizer)

    def set_audio_filters(self, compressor: bool, spatializer: bool) -> None:
        changed = self._audio_filters != (compressor, spatializer)
        self._audio_filters = (compressor, spatializer)
        if changed and self.current_path:
            self.reload_current()

    def set_sharpen(self, amount: float) -> None:
        self._sharpen = amount
        if self.current_path:
            self.reload_current()

    def set_aspect_ratio(self, value: str | None) -> None:
        self.player.video_set_aspect_ratio(value)

    def set_crop(self, value: str | None) -> None:
        self.player.video_set_crop_geometry(value)

    def show_converter(self) -> None:
        input_path = (
            self.current_path
            if self.current_path and Path(self.current_path).is_file()
            else None
        )
        dialog = ConverterDialog(
            self.application_controller.vlc_executable, input_path, self
        )
        dialog.show()
        self._keep_dialog(dialog)

    # ---------- window, skins, information ----------

    def eventFilter(self, watched, event) -> bool:
        if self._fullscreen and event.type() in {
            QEvent.Type.KeyPress,
            QEvent.Type.ShortcutOverride,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.Wheel,
        }:
            self._show_fullscreen_controls()
        return super().eventFilter(watched, event)

    def _poll_fullscreen_activity(self) -> None:
        if not self._fullscreen:
            return
        position = QCursor.pos()
        if position != self._fullscreen_cursor_position:
            self._fullscreen_cursor_position = position
            self._show_fullscreen_controls()

    def _show_fullscreen_controls(self) -> None:
        if not self._fullscreen:
            return
        self.fullscreen_hide_timer.start()
        if self._fullscreen_controls_visible:
            return
        self._fullscreen_controls_visible = True
        target_height = max(1, self.controls.sizeHint().height())
        self.controls.setMaximumHeight(0)
        self.controls.show()
        self._animate_controls(0, target_height, hide_when_done=False)

    def _hide_fullscreen_controls(self) -> None:
        if not self._fullscreen or not self._fullscreen_controls_visible:
            return
        if self.controls.rect().contains(
            self.controls.mapFromGlobal(QCursor.pos())
        ):
            self.fullscreen_hide_timer.start(750)
            return
        self._fullscreen_controls_visible = False
        self._animate_controls(
            self.controls.height(), 0, hide_when_done=True
        )

    def _animate_controls(
        self, start: int, end: int, hide_when_done: bool
    ) -> None:
        if self._controls_animation is not None:
            self._controls_animation.stop()
            self._controls_animation.deleteLater()
        animation = QPropertyAnimation(self.controls, b"maximumHeight", self)
        self._controls_animation = animation
        animation.setDuration(180)
        animation.setStartValue(max(0, start))
        animation.setEndValue(max(0, end))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def finish() -> None:
            if self._controls_animation is not animation:
                return
            if hide_when_done and not self._fullscreen_controls_visible:
                self.controls.hide()
            else:
                self.controls.setMaximumHeight(16777215)
            animation.deleteLater()
            self._controls_animation = None

        animation.finished.connect(finish)
        animation.start()

    def _set_fullscreen_pane_chrome(self, hidden: bool) -> None:
        self.video_grid.setSpacing(0 if hidden else 3)
        for pane in self.panes:
            pane.header.setVisible(not hidden)
            layout = pane.container.layout()
            margin = 0 if hidden else 3
            layout.setContentsMargins(margin, margin, margin, margin)
            layout.setSpacing(0 if hidden else 3)
        self.set_active_pane(self.active_pane)

    def toggle_fullscreen(self) -> None:
        if self._fullscreen:
            self.leave_fullscreen()
            return
        self._fullscreen = True
        self._window_was_maximized = self.isMaximized()
        self._sidebar_was_visible = self.sidebar.isVisible()
        self._fullscreen_controls_visible = False
        self._fullscreen_cursor_position = QCursor.pos()
        self._set_fullscreen_pane_chrome(True)
        self.controls.setMaximumHeight(16777215)
        self.controls.hide()
        self.sidebar.hide()
        self.menuBar().hide()
        self.statusBar().hide()
        self.showFullScreen()
        self.fullscreen_activity_timer.start()

    def leave_fullscreen(self) -> None:
        if not self._fullscreen:
            return
        self._fullscreen = False
        self.fullscreen_activity_timer.stop()
        self.fullscreen_hide_timer.stop()
        if self._controls_animation is not None:
            self._controls_animation.stop()
            self._controls_animation.deleteLater()
            self._controls_animation = None
        self._fullscreen_controls_visible = False
        self.controls.setMaximumHeight(16777215)
        self.controls.show()
        self._set_fullscreen_pane_chrome(False)
        self.menuBar().show()
        self.statusBar().show()
        self.sidebar.setVisible(self._sidebar_was_visible)
        if self._window_was_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    def import_skin(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import QSS skin", "", "Qt stylesheets (*.qss)"
        )
        if path:
            self.application_controller.apply_custom_skin(path)

    def show_shortcut_editor(self) -> None:
        portable = QKeySequence.SequenceFormat.PortableText
        current = {
            shortcut_id: action.shortcut().toString(portable)
            for shortcut_id, action in self.shortcut_actions.items()
        }
        dialog = ShortcutEditorDialog(
            SHORTCUT_DEFINITIONS, current, self
        )
        if not dialog.exec():
            return
        for shortcut_id, sequence in dialog.selected_shortcuts().items():
            self.settings.setValue(f"shortcuts/{shortcut_id}", sequence)
            action = self.shortcut_actions.get(shortcut_id)
            if action is not None:
                action.setShortcut(QKeySequence(sequence))
        self.settings.sync()
        self.statusBar().showMessage("Keyboard shortcuts updated.", 3000)

    def _shortcut_text(self, shortcut_id: str) -> str:
        action = self.shortcut_actions.get(shortcut_id)
        if action is None:
            return ""
        return action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)

    def show_controls(self) -> None:
        QMessageBox.information(
            self,
            "Controls",
            f"{self._shortcut_text('play_pause')} — Play/pause\n"
            f"{self._shortcut_text('seek_back_5')} / "
            f"{self._shortcut_text('seek_forward_5')} — "
            f"Skip {self._skip_seconds} seconds\n"
            f"{self._shortcut_text('seek_back_30')} / "
            f"{self._shortcut_text('seek_forward_30')} — Seek 30 seconds\n"
            f"{self._shortcut_text('volume_up')} / "
            f"{self._shortcut_text('volume_down')} — Volume\n"
            f"{self._shortcut_text('next_frame')} — Next frame\n"
            f"{self._shortcut_text('set_a')} / "
            f"{self._shortcut_text('set_b')} — Set A/B loop points\n"
            f"{self._shortcut_text('clear_ab')} — Clear A/B loop\n"
            f"{self._shortcut_text('fullscreen')} or double-click video — "
            "Enter/leave fullscreen\n"
            f"{self._shortcut_text('leave_fullscreen')} — Leave fullscreen\n"
            "Right-drag horizontally — Seek\n"
            "Right-drag vertically — Volume\n"
            f"{self._shortcut_text('add_pane')} — Add video pane (maximum four)\n"
            "Click a pane — Make it active\n"
            "Pane play button — Pause/resume only that video\n"
            f"{self._shortcut_text('play_pause_all')} — Play/pause all panes\n"
            f"{self._shortcut_text('toggle_sidebar')} — Show/hide sidebar\n"
            "Click timeline — Seek directly to that time\n"
            "Hover timeline — Preview the exact time\n"
            "Click or hover volume — Set or preview the level\n"
            "Drop files or folders on a pane — Open them there\n\n"
            "Change the skip amount under Settings → Playback skip amount.\n"
            "Change shortcuts under View → Customize keyboard shortcuts.",
        )

    def show_about(self) -> None:
        version = decode_label(vlc.libvlc_get_version())
        QMessageBox.about(
            self,
            "Aurora Player",
            f"<b>Aurora Player {__version__}</b><br>"
            f"Cross-platform media player powered by Qt and libVLC {version}.<br><br>"
            "One window can play up to four videos in a 2×2 grid.",
        )

    def _keep_dialog(self, dialog: QWidget) -> None:
        self._dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda: self._dialogs.remove(dialog) if dialog in self._dialogs else None
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._cleanup_done:
            self.application_controller.window_closed(self)
            event.accept()
            return
        if self._cleanup_started:
            event.ignore()
            return
        self._cleanup_started = True
        self.thumbnail_provider.stop()
        for pane in self.panes:
            self._save_resume_position(pane, force=True)
            self._quiesce_pane(pane)
        self.timer.stop()
        self.pane_selection_timer.stop()
        self.settings.sync()
        self.application_controller.settings.sync()
        self.hide()
        event.ignore()
        for pane in self.panes:
            self._vlc_cleanup.release_player(pane.player)
        self._vlc_cleanup.finish(
            self._vlc_instance, self.cleanup_finished.emit
        )
        # Native audio drivers should now close sequentially. If a third-party
        # driver still blocks VLC forever, do not leave an invisible process
        # behind after the user has explicitly exited the application.
        QTimer.singleShot(5000, self._force_close_after_cleanup_timeout)

    def _force_close_after_cleanup_timeout(self) -> None:
        if self._cleanup_done:
            return
        self.settings.sync()
        self.application_controller.settings.sync()
        os._exit(0)

    def _complete_close(self) -> None:
        if self._cleanup_done:
            return
        self._cleanup_done = True
        self.close()
