from __future__ import annotations

import threading
import time

from aurora_player.player import SerialVlcCleanup


def test_vlc_cleanup_is_serial_and_ordered() -> None:
    calls: list[str] = []
    state_lock = threading.Lock()
    active = 0
    maximum_active = 0
    finished = threading.Event()

    class FakeNativeObject:
        def __init__(self, name: str) -> None:
            self.name = name

        def stop(self) -> None:
            nonlocal active, maximum_active
            with state_lock:
                active += 1
                maximum_active = max(maximum_active, active)
                calls.append(f"stop:{self.name}")
            time.sleep(0.02)
            with state_lock:
                active -= 1

        def release(self) -> None:
            calls.append(f"release:{self.name}")

    cleanup = SerialVlcCleanup()
    cleanup.release_player(FakeNativeObject("first"))
    cleanup.release_player(FakeNativeObject("second"))
    cleanup.finish(FakeNativeObject("instance"), finished.set)

    assert finished.wait(2)
    assert maximum_active == 1
    assert calls == [
        "stop:first",
        "release:first",
        "stop:second",
        "release:second",
        "release:instance",
    ]
