from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator import arrangement_edit_history_ui as media_ui
from rocksmith_cdlc_generator.arrangement_edit_history_ui import (
    ArrangementEditHistorySongWorkspaceWindow,
)


class _Var:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _Scale:
    def __init__(self) -> None:
        self.to = None

    def configure(self, **kwargs) -> None:
        self.to = kwargs.get("to", self.to)


class _Transport:
    duration_seconds = 120.0
    sample_rate_hz = 44100
    channels = 2

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Thread:
    instances: list["_Thread"] = []

    def __init__(self, *, target, daemon: bool, name: str) -> None:
        self.target = target
        self.daemon = daemon
        self.name = name
        self.started = False
        self.__class__.instances.append(self)

    def start(self) -> None:
        self.started = True


def _workspace(project: Path):
    window = object.__new__(ArrangementEditHistorySongWorkspaceWindow)
    window.project = project.resolve()
    window.transport = None
    window.waveform = None
    window._media_project = None
    window._media_load_generation = 0
    window._media_loading_project = None
    window.media_status_var = _Var()
    window.seek_scale = _Scale()
    window._sync_media_controls = lambda: None
    window._draw_timeline = lambda: None
    callbacks = []
    window.after = lambda _delay, callback: callbacks.append(callback)
    return window, callbacks


def test_ensure_media_starts_worker_without_building_waveform_inline(tmp_path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    window, callbacks = _workspace(project)
    calls: list[Path] = []
    waveform = object()
    transport = _Transport()

    monkeypatch.setattr(media_ui.threading, "Thread", _Thread)
    monkeypatch.setattr(
        media_ui,
        "load_or_build_waveform",
        lambda selected: calls.append(selected) or waveform,
    )
    monkeypatch.setattr(media_ui, "ProjectAudioTransport", lambda _selected: transport)
    _Thread.instances.clear()

    window._ensure_media()

    assert calls == []
    assert len(_Thread.instances) == 1
    assert _Thread.instances[0].started is True
    assert window.media_status_var.value == "Preparing waveform + playback in background…"

    _Thread.instances[0].target()
    assert calls == [project.resolve()]
    assert len(callbacks) == 1

    callbacks[0]()
    assert window.waveform is waveform
    assert window.transport is transport
    assert window._media_project == project.resolve()
    assert window.seek_scale.to == 120.0
    assert "44.1 kHz" in window.media_status_var.value


def test_late_media_result_for_previous_project_is_discarded(tmp_path, monkeypatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    window, callbacks = _workspace(first)
    waveform = object()
    transport = _Transport()

    monkeypatch.setattr(media_ui.threading, "Thread", _Thread)
    monkeypatch.setattr(media_ui, "load_or_build_waveform", lambda _selected: waveform)
    monkeypatch.setattr(media_ui, "ProjectAudioTransport", lambda _selected: transport)
    _Thread.instances.clear()

    window._ensure_media()
    _Thread.instances[0].target()
    assert len(callbacks) == 1

    window.project = second.resolve()
    window._media_load_generation += 1
    window._media_loading_project = None
    callbacks[0]()

    assert transport.closed is True
    assert window.transport is None
    assert window.waveform is None
    assert window._media_project is None
