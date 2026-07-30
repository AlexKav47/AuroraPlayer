from pathlib import Path

from aurora_player.library import LibraryStore, load_m3u, save_m3u
from aurora_player.player import format_time


def test_library_add_search_and_remove(tmp_path: Path) -> None:
    media = tmp_path / "example movie.mp4"
    media.write_bytes(b"not-a-real-video")
    store = LibraryStore(tmp_path / "library.sqlite3")
    assert store.add_paths([media]) == 1
    assert [item.title for item in store.items("movie")] == ["example movie"]
    store.remove(str(media.resolve()))
    assert store.items() == []
    store.close()


def test_library_folder_tracking_and_removal(tmp_path: Path) -> None:
    folder = tmp_path / "Videos"
    nested = folder / "Series"
    nested.mkdir(parents=True)
    first = folder / "movie.mp4"
    second = nested / "episode.mkv"
    outside = tmp_path / "outside.mp3"
    for media in (first, second, outside):
        media.write_bytes(b"test")

    store = LibraryStore(tmp_path / "folder-library.sqlite3")
    assert store.scan_folder(folder) == 2
    assert store.add_paths([outside]) == 1
    assert store.folders() == [str(folder.resolve())]
    assert store.remove_folder(folder) == 2
    assert store.folders() == []
    assert [item.path for item in store.items()] == [str(outside.resolve())]
    assert first.exists() and second.exists()
    store.close()


def test_m3u_round_trip(tmp_path: Path) -> None:
    media = tmp_path / "track.flac"
    media.write_bytes(b"test")
    playlist = tmp_path / "list.m3u8"
    save_m3u(playlist, [str(media)])
    assert load_m3u(playlist) == [str(media.resolve())]


def test_format_time() -> None:
    assert format_time(0) == "0:00"
    assert format_time(65_000) == "1:05"
    assert format_time(3_665_000) == "1:01:05"
