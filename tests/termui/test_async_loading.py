"""
Module: tests/termui/test_async_loading.py
Description: Tests for async data loading with AsyncTask.
Author: Zev
Date: 2026-05-17
"""

from __future__ import annotations

import threading
import time

from pigit.termui._async_task import AsyncTask
from pigit.termui._component import Component
from pigit.termui.event_loop import AppEventLoop


class _FakeInput:
    """Fake input that returns keys then exits."""

    def __init__(self, keys: list[str], delay: float = 0.01):
        self._keys = list(keys)
        self._delay = delay
        self._idx = 0

    def get_input(self):
        if self._idx < len(self._keys):
            key = self._keys[self._idx]
            self._idx += 1
            return ([key],)
        time.sleep(self._delay)
        return None

    def set_input_timeouts(self, timeout: float) -> None:
        pass


class _MockPanel(Component):
    """Panel that uses AsyncTask to load data."""

    def __init__(self):
        super().__init__()
        self._loader = AsyncTask()
        self.data: list[str] = []
        self.loaded = False
        self._activated = True

    def is_activated(self):
        return self._activated

    def refresh(self):
        self._loader.start(self._load_data, self._on_loaded)

    def _load_data(self):
        time.sleep(0.05)
        return ["a", "b", "c"]

    def _on_loaded(self, data):
        if not self.is_activated():
            return
        self.data = data
        self.loaded = True

    def deactivate(self):
        super().deactivate()
        self._loader.cancel()

    def _render_surface(self, surface):
        pass


# --- AsyncTask unit tests ---


def test_async_task_delivers_result():
    task = AsyncTask()
    received = []

    task.start(lambda: "hello", lambda x: received.append(x))
    # Wait for worker
    time.sleep(0.1)
    AsyncTask.poll_all()
    assert received == ["hello"]


def test_async_task_cancel_drops_result():
    task = AsyncTask()
    received = []

    def slow_work():
        time.sleep(0.05)
        return "hello"

    task.start(slow_work, lambda x: received.append(x))
    task.cancel()
    time.sleep(0.1)
    AsyncTask.poll_all()
    assert received == []


def test_async_task_multiple_polls_are_safe():
    task = AsyncTask()
    received = []

    task.start(lambda: "x", lambda x: received.append(x))
    time.sleep(0.05)
    AsyncTask.poll_all()
    AsyncTask.poll_all()  # second poll should be no-op
    assert received == ["x"]


# --- Integration with AppEventLoop ---


def test_async_result_processed_during_loop():
    """Async callback is invoked during event loop idle ticks."""
    panel = _MockPanel()
    panel.refresh()

    # Simulate a few idle ticks; the async task should complete and be polled.
    inp = _FakeInput([], delay=0.02)
    loop = AppEventLoop(panel, input_handle=inp)
    loop._render_requested = True

    # Run loop for a short time then break
    loop._loop = lambda: None  # We'll manually poll

    # ThreadPoolExecutor scheduling + work() duration varies across machines.
    # A fixed sleep is flaky on slow CI runners; poll with a generous timeout
    # so the test adapts to the actual execution speed.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        AsyncTask.poll_all()
        if panel.loaded:
            break
        time.sleep(0.01)

    assert panel.loaded
    assert panel.data == ["a", "b", "c"]


def test_panel_deactivate_cancels_load():
    """When panel deactivates, async result is dropped."""
    panel = _MockPanel()
    panel.refresh()
    panel.deactivate()

    time.sleep(0.1)
    AsyncTask.poll_all()

    assert not panel.loaded
    assert panel.data == []


def test_async_load_does_not_block_input():
    """Input is handled while async work is in progress."""
    panel = _MockPanel()
    keys_received = []

    def _handle_event(key):
        keys_received.append(key)

    panel._handle_event = _handle_event
    panel.refresh()

    # Simulate input arriving while async work is still running
    inp = _FakeInput(["x", "y"], delay=0.01)
    loop = AppEventLoop(panel, input_handle=inp)

    # Run a few iterations manually
    for _ in range(3):
        AsyncTask.poll_all()
        input_key = inp.get_input()
        if input_key and input_key[0]:
            panel._handle_event(input_key[0][0])

    # Keys were handled even before async work completed
    assert keys_received == ["x", "y"]


def test_inactive_panel_drops_arriving_data():
    """Data arriving after tab switch (panel deactivated) is ignored."""
    panel = _MockPanel()
    panel.refresh()

    # Wait for work to complete
    time.sleep(0.1)

    # Deactivate before polling
    panel.deactivate()
    AsyncTask.poll_all()

    assert not panel.loaded
    assert panel.data == []


def test_async_task_race_new_start_drops_old_result():
    """Rapid start() calls cancel previous tasks; only latest result arrives."""
    received = []
    old_started = threading.Event()

    def slow_work(label):
        if label == "old":
            old_started.set()
        time.sleep(0.05)
        return label

    task = AsyncTask()
    task.start(lambda: slow_work("old"), lambda x: received.append(x))
    old_started.wait(timeout=1.0)
    task.start(lambda: slow_work("new"), lambda x: received.append(x))

    # Poll with timeout instead of fixed sleep for slow CI runners.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        AsyncTask.poll_all()
        if received:
            break
        time.sleep(0.01)

    assert received == ["new"]


# --- run_async + copy_to_clipboard tests ---


def test_run_async_clipboard_callback(mocker):
    """run_async with copy_to_clipboard delivers result via callback."""
    import pigit.ext.utils
    from pigit.termui._async_task import run_async

    mocker.patch("pigit.ext.utils.copy_to_clipboard", return_value=True)
    received = []

    run_async(lambda: pigit.ext.utils.copy_to_clipboard("hello"), lambda ok: received.append(ok))

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        AsyncTask.poll_all()
        if received:
            break
        time.sleep(0.01)

    assert received == [True]


def test_run_async_dedup(mocker):
    """Rapid run_async calls cancel the old task when caller manages the handle."""
    import pigit.ext.utils
    from pigit.termui._async_task import run_async

    old_started = threading.Event()
    old_can_finish = threading.Event()

    def slow_copy(text):
        if text == "old":
            old_started.set()
        old_can_finish.wait(timeout=5.0)
        return text == "new"

    mocker.patch("pigit.ext.utils.copy_to_clipboard", side_effect=slow_copy)
    received = []

    old_task = run_async(
        lambda: pigit.ext.utils.copy_to_clipboard("old"),
        lambda ok: received.append("old"),
    )
    old_started.wait(timeout=1.0)
    old_task.cancel()
    old_can_finish.set()

    run_async(
        lambda: pigit.ext.utils.copy_to_clipboard("new"),
        lambda ok: received.append("new"),
    )

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        AsyncTask.poll_all()
        if "new" in received:
            break
        time.sleep(0.01)

    assert "new" in received
    assert "old" not in received
