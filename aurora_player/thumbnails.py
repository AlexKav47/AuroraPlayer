from __future__ import annotations

import ctypes
import hashlib
import os
import queue
import sys
import threading
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QSize,
    QStandardPaths,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from .library import MEDIA_EXTENSIONS


AUDIO_EXTENSIONS = {
    ".aac",
    ".ac3",
    ".aiff",
    ".alac",
    ".ape",
    ".dts",
    ".eac3",
    ".flac",
    ".m4a",
    ".mka",
    ".mp2",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}
VIDEO_EXTENSIONS = MEDIA_EXTENSIONS - AUDIO_EXTENSIONS
THUMBNAIL_SIZE = QSize(112, 63)


def thumbnail_cache_key(path: str | Path, size: QSize = THUMBNAIL_SIZE) -> str:
    """Return a cache key that changes whenever the source file changes."""
    source = Path(path).expanduser().resolve()
    try:
        stat = source.stat()
        fingerprint = (
            f"{source}|{stat.st_size}|{stat.st_mtime_ns}|"
            f"{size.width()}x{size.height()}"
        )
    except OSError:
        fingerprint = f"{source}|missing|{size.width()}x{size.height()}"
    return hashlib.sha256(fingerprint.encode("utf-8", "surrogatepass")).hexdigest()


def thumbnail_cache_directory() -> Path:
    portable_root = os.environ.get("AURORA_DATA_DIR")
    if portable_root:
        root = Path(portable_root).expanduser().resolve() / "thumbnails"
    else:
        cache_root = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation
        )
        root = Path(cache_root) / "thumbnails"
    root.mkdir(parents=True, exist_ok=True)
    return root


def media_placeholder(
    path: str | Path, size: QSize = THUMBNAIL_SIZE
) -> QImage:
    """Create a compact fallback card for audio and unavailable thumbnails."""
    source = Path(path)
    is_video = source.suffix.lower() in VIDEO_EXTENSIONS
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#17202b"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    accent = QColor("#82aaff") if is_video else QColor("#9fe6c8")
    painter.fillRect(0, 0, 5, size.height(), accent)
    painter.setPen(QPen(QColor("#263545"), 1))
    painter.drawRoundedRect(0, 0, size.width() - 1, size.height() - 1, 5, 5)

    if is_video:
        center_x = size.width() // 2 + 2
        center_y = size.height() // 2
        triangle = QPainterPath()
        triangle.moveTo(center_x - 8, center_y - 11)
        triangle.lineTo(center_x + 11, center_y)
        triangle.lineTo(center_x - 8, center_y + 11)
        triangle.closeSubpath()
        painter.fillPath(triangle, accent)
    else:
        note_pen = QPen(accent, 4)
        note_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(note_pen)
        painter.drawLine(size.width() // 2 - 4, 18, size.width() // 2 - 4, 42)
        painter.drawLine(size.width() // 2 - 4, 18, size.width() // 2 + 12, 14)
        painter.drawEllipse(size.width() // 2 - 13, 38, 11, 9)
        painter.drawEllipse(size.width() // 2 + 3, 34, 11, 9)

    painter.setPen(QColor("#dce7f4"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(7)
    painter.setFont(font)
    extension = source.suffix.upper().lstrip(".")[:6] or "MEDIA"
    painter.drawText(10, size.height() - 8, extension)
    painter.end()
    return image


class ThumbnailProvider(QObject):
    """Load cached thumbnails and generate missing ones outside the UI thread."""

    ready = Signal(str, QImage)
    _generated = Signal(str, QImage)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.cache_root = thumbnail_cache_directory()
        self._pending: set[str] = set()
        self._jobs: queue.Queue[tuple[str, Path] | None] = queue.Queue()
        self._stopped = False
        self._generated.connect(self._worker_finished)
        self._threads = [
            threading.Thread(
                target=self._run,
                name=f"aurora-thumbnail-{index + 1}",
                daemon=True,
            )
            for index in range(2)
        ]
        for worker in self._threads:
            worker.start()

    def request(self, path: str | Path) -> None:
        source = str(Path(path).expanduser().resolve())
        if Path(source).suffix.lower() not in VIDEO_EXTENSIONS:
            return
        cache_path = self.cache_root / f"{thumbnail_cache_key(source)}.png"
        if cache_path.is_file():
            image = QImage(str(cache_path))
            if not image.isNull():
                self.ready.emit(source, image)
                return
        if (
            self._stopped
            or source in self._pending
            or not Path(source).is_file()
        ):
            return
        self._pending.add(source)
        self._jobs.put((source, cache_path))

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                self._jobs.task_done()
                return
            path, cache_path = job
            image = QImage()
            try:
                image = _windows_shell_thumbnail(path, THUMBNAIL_SIZE)
                if not image.isNull() and not self._stopped:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(str(cache_path), "PNG")
            except Exception:
                image = QImage()
            if not self._stopped:
                self._generated.emit(path, image)
            self._jobs.task_done()

    def _worker_finished(self, path: str, image: QImage) -> None:
        self._pending.discard(path)
        if not image.isNull():
            self.ready.emit(path, image)

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        for _ in self._threads:
            self._jobs.put(None)


def _windows_shell_thumbnail(path: str, size: QSize) -> QImage:
    """Ask Windows Explorer's thumbnail provider for a video preview."""
    if sys.platform != "win32":
        return QImage()

    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class SIZE(ctypes.Structure):
        _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

    class BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", wintypes.LONG),
            ("bmWidth", wintypes.LONG),
            ("bmHeight", wintypes.LONG),
            ("bmWidthBytes", wintypes.LONG),
            ("bmPlanes", wintypes.WORD),
            ("bmBitsPixel", wintypes.WORD),
            ("bmBits", wintypes.LPVOID),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class RGBQUAD(ctypes.Structure):
        _fields_ = [
            ("rgbBlue", ctypes.c_ubyte),
            ("rgbGreen", ctypes.c_ubyte),
            ("rgbRed", ctypes.c_ubyte),
            ("rgbReserved", ctypes.c_ubyte),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]

    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    gdi32 = ctypes.windll.gdi32
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.IIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(GUID)]
    ole32.IIDFromString.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.restype = wintypes.BOOL
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    gdi32.GetObjectW.restype = ctypes.c_int
    gdi32.GetDIBits.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(BITMAPINFO),
        wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    initialize_result = ole32.CoInitializeEx(None, 0x2)
    initialized = initialize_result in (0, 1)
    if initialize_result < 0:
        return QImage()
    factory = ctypes.c_void_p()
    bitmap_handle = wintypes.HANDLE()
    try:
        iid = GUID()
        if ole32.IIDFromString(
            "{BCC18B79-BA16-442F-80C4-8A59C30C463B}", ctypes.byref(iid)
        ) < 0:
            return QImage()
        shell32.SHCreateItemFromParsingName.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_void_p,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHCreateItemFromParsingName.restype = ctypes.c_long
        if shell32.SHCreateItemFromParsingName(
            path, None, ctypes.byref(iid), ctypes.byref(factory)
        ) < 0:
            return QImage()

        vtable = ctypes.cast(
            factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        get_image_type = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            SIZE,
            ctypes.c_uint,
            ctypes.POINTER(wintypes.HANDLE),
        )
        get_image = get_image_type(vtable[3])
        # THUMBNAILONLY | BIGGERSIZEOK lets Explorer use its persistent cache.
        if get_image(
            factory,
            SIZE(size.width(), size.height()),
            0x8 | 0x1,
            ctypes.byref(bitmap_handle),
        ) < 0 or not bitmap_handle:
            return QImage()

        bitmap = BITMAP()
        if not gdi32.GetObjectW(
            bitmap_handle, ctypes.sizeof(bitmap), ctypes.byref(bitmap)
        ):
            return QImage()
        width, height = int(bitmap.bmWidth), abs(int(bitmap.bmHeight))
        if width <= 0 or height <= 0:
            return QImage()

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        device_context = gdi32.CreateCompatibleDC(None)
        try:
            copied = gdi32.GetDIBits(
                device_context,
                bitmap_handle,
                0,
                height,
                buffer,
                ctypes.byref(info),
                0,
            )
        finally:
            gdi32.DeleteDC(device_context)
        if copied != height:
            return QImage()
        image = QImage(
            buffer.raw,
            width,
            height,
            width * 4,
            QImage.Format.Format_RGB32,
        ).copy()
        if image.size() != size:
            image = image.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            left = max(0, (image.width() - size.width()) // 2)
            top = max(0, (image.height() - size.height()) // 2)
            image = image.copy(left, top, size.width(), size.height())
        return image
    finally:
        if bitmap_handle:
            gdi32.DeleteObject(bitmap_handle)
        if factory:
            vtable = ctypes.cast(
                factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
            ).contents
            release_type = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
            release_type(vtable[2])(factory)
        if initialized:
            ole32.CoUninitialize()
