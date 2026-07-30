from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QStandardPaths


MEDIA_EXTENSIONS = {
    ".3g2",
    ".3gp",
    ".aac",
    ".ac3",
    ".aiff",
    ".alac",
    ".ape",
    ".asf",
    ".avi",
    ".divx",
    ".dts",
    ".eac3",
    ".flac",
    ".flv",
    ".m2ts",
    ".m4a",
    ".m4v",
    ".mka",
    ".mkv",
    ".mov",
    ".mp2",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ogg",
    ".ogm",
    ".ogv",
    ".opus",
    ".rm",
    ".rmvb",
    ".ts",
    ".vob",
    ".wav",
    ".webm",
    ".wma",
    ".wmv",
}


def expand_media_paths(paths: Iterable[str | Path]) -> list[str]:
    """Resolve dropped files and recursively expand dropped folders."""
    media: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        candidates = (
            (path,)
            if path.is_file()
            else (
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file()
            )
            if path.is_dir()
            else ()
        )
        for candidate in candidates:
            if candidate.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            normalized = str(candidate.resolve())
            if normalized not in seen:
                seen.add(normalized)
                media.append(normalized)
    return sorted(media, key=str.casefold)


@dataclass(slots=True)
class LibraryItem:
    path: str
    title: str
    kind: str
    size: int
    modified: float


class LibraryStore:
    def __init__(self, database_path: Path | None = None) -> None:
        if database_path is None:
            portable_root = os.environ.get("AURORA_DATA_DIR")
            root = (
                Path(portable_root).expanduser().resolve()
                if portable_root
                else Path(
                    QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.AppDataLocation
                    )
                )
            )
            root.mkdir(parents=True, exist_ok=True)
            database_path = root / "library.sqlite3"
        self.path = database_path
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS media (
                path TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                size INTEGER NOT NULL,
                modified REAL NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS folders (
                path TEXT PRIMARY KEY,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS playback_positions (
                location TEXT PRIMARY KEY,
                position_ms INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def add_paths(self, paths: Iterable[str | Path]) -> int:
        rows: list[tuple[str, str, str, int, float]] = []
        for raw_path in paths:
            path = Path(raw_path).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            stat = path.stat()
            kind = "Audio" if path.suffix.lower() in {
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
            } else "Video"
            rows.append((str(path), path.stem, kind, stat.st_size, stat.st_mtime))
        self.connection.executemany(
            """
            INSERT INTO media(path, title, kind, size, modified)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title=excluded.title,
                kind=excluded.kind,
                size=excluded.size,
                modified=excluded.modified
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def scan_folder(self, folder: str | Path) -> int:
        root = Path(folder).expanduser().resolve()
        if not root.is_dir():
            return 0
        self.connection.execute(
            "INSERT OR IGNORE INTO folders(path) VALUES (?)", (str(root),)
        )
        self.connection.commit()
        return self.add_paths(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
        )

    def folders(self) -> list[str]:
        return [
            str(row["path"])
            for row in self.connection.execute(
                "SELECT path FROM folders ORDER BY path COLLATE NOCASE"
            )
        ]

    def items(self, search: str = "") -> list[LibraryItem]:
        query = "SELECT path, title, kind, size, modified FROM media"
        params: tuple[str, ...] = ()
        if search.strip():
            query += " WHERE title LIKE ? OR path LIKE ?"
            needle = f"%{search.strip()}%"
            params = (needle, needle)
        query += " ORDER BY title COLLATE NOCASE"
        return [LibraryItem(**dict(row)) for row in self.connection.execute(query, params)]

    def remove(self, path: str) -> None:
        self.connection.execute("DELETE FROM media WHERE path = ?", (path,))
        self.connection.commit()

    def remove_paths(self, paths: Iterable[str | Path]) -> int:
        normalized = {str(Path(path).expanduser().resolve()) for path in paths}
        if not normalized:
            return 0
        before = self.connection.total_changes
        self.connection.executemany(
            "DELETE FROM media WHERE path = ?",
            ((path,) for path in normalized),
        )
        self.connection.commit()
        return self.connection.total_changes - before

    def remove_folder(self, folder: str | Path) -> int:
        root = Path(folder).expanduser().resolve()
        media_paths = [
            str(row["path"])
            for row in self.connection.execute("SELECT path FROM media")
            if Path(str(row["path"])).is_relative_to(root)
        ]
        removed = self.remove_paths(media_paths)
        folder_paths = [
            str(row["path"])
            for row in self.connection.execute("SELECT path FROM folders")
            if Path(str(row["path"])).is_relative_to(root)
        ]
        self.connection.executemany(
            "DELETE FROM folders WHERE path = ?",
            ((path,) for path in folder_paths),
        )
        self.connection.commit()
        return removed

    def playback_position(self, location: str) -> tuple[int, int] | None:
        row = self.connection.execute(
            """
            SELECT position_ms, duration_ms
            FROM playback_positions
            WHERE location = ?
            """,
            (location,),
        ).fetchone()
        if row is None:
            return None
        return int(row["position_ms"]), int(row["duration_ms"])

    def save_playback_position(
        self, location: str, position_ms: int, duration_ms: int
    ) -> None:
        position_ms = max(0, int(position_ms))
        duration_ms = max(0, int(duration_ms))
        # Starting over, or reaching the final few seconds, should make the next
        # launch begin at the start instead of resuming an already-finished item.
        if (
            position_ms < 10_000
            or (
                duration_ms > 0
                and position_ms
                >= min(duration_ms - 15_000, duration_ms * 0.95)
            )
        ):
            self.clear_playback_position(location)
            return
        self.connection.execute(
            """
            INSERT INTO playback_positions(location, position_ms, duration_ms)
            VALUES (?, ?, ?)
            ON CONFLICT(location) DO UPDATE SET
                position_ms=excluded.position_ms,
                duration_ms=excluded.duration_ms,
                updated_at=CURRENT_TIMESTAMP
            """,
            (location, position_ms, duration_ms),
        )
        self.connection.commit()

    def clear_playback_position(self, location: str) -> None:
        self.connection.execute(
            "DELETE FROM playback_positions WHERE location = ?", (location,)
        )
        self.connection.commit()

    def clear_playback_positions(self) -> None:
        self.connection.execute("DELETE FROM playback_positions")
        self.connection.commit()


def save_m3u(path: str | Path, media_paths: Iterable[str]) -> None:
    target = Path(path)
    content = "#EXTM3U\n" + "\n".join(media_paths) + "\n"
    target.write_text(content, encoding="utf-8")


def load_m3u(path: str | Path) -> list[str]:
    result: list[str] = []
    source = Path(path)
    for line in source.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            candidate = Path(line)
            if not candidate.is_absolute():
                candidate = source.parent / candidate
            result.append(str(candidate.resolve()))
    return result


def save_playlist_json(path: str | Path, media_paths: Iterable[str]) -> None:
    Path(path).write_text(json.dumps(list(media_paths), indent=2), encoding="utf-8")
