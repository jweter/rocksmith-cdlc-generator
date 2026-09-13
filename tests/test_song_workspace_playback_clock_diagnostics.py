from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator import song_workspace_playback_ui as playback_ui
from rocksmith_cdlc_generator.song_workspace_playback_ui import PlaybackSongWorkspaceWindow


def _window(tmp_path: Path) -> PlaybackSongWorkspaceWindow:
    window = object.__new__(PlaybackSongWorkspaceWindow)
    window.project = tmp_path
    window._last_clock_sample = None
    window._active_clock_anomaly_code = None
    return window


def _diagnostics(tmp_path: Path) -> list[dict]:
    path = tmp_path / "review" / "desktop_diagnostics.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _patch_clock(monkeypatch: pytest.MonkeyPatch, values: list[float]) -> None:
    iterator = iter(values)
    monkeypatch.setattr(playback_ui.time, "monotonic", lambda: next(iterator))


def test_first_sample_never_flags_without_a_prior_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _window(tmp_path)
    _patch_clock(monkeypatch, [0.0])

    window._check_playback_clock(0.0)

    assert window._last_clock_sample is not None
    assert _diagnostics(tmp_path) == []


def test_steady_playback_never_persists_a_diagnostic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    window = _window(tmp_path)
    _patch_clock(monkeypatch, [0.0, 0.05, 0.10, 0.15, 0.20])

    for position in (0.0, 0.05, 0.10, 0.15, 0.20):
        window._check_playback_clock(position)

    assert _diagnostics(tmp_path) == []


def test_backward_jump_persists_exactly_one_diagnostic_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(tmp_path)
    _patch_clock(monkeypatch, [0.0, 0.05, 0.10, 0.15])

    window._check_playback_clock(5.0)
    window._check_playback_clock(5.05)
    window._check_playback_clock(4.20)  # backward jump, wall still advancing normally
    window._check_playback_clock(4.15)  # still moving backward relative to the pre-jump peak

    entries = _diagnostics(tmp_path)
    assert len(entries) == 1
    assert entries[0]["level"] == "ERROR"
    assert "clock_backward_jump" in entries[0]["message"]


def test_recovering_to_normal_playback_rearms_detection_for_a_later_episode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(tmp_path)
    _patch_clock(monkeypatch, [0.0, 0.05, 0.10, 0.15, 0.20, 0.25])

    window._check_playback_clock(1.0)
    window._check_playback_clock(1.05)
    window._check_playback_clock(0.20)  # first backward-jump episode
    window._check_playback_clock(0.25)  # normal advance again -> clears the active anomaly
    window._check_playback_clock(0.05)  # second, independent backward-jump episode
    window._check_playback_clock(0.10)

    entries = _diagnostics(tmp_path)
    assert len(entries) == 2
    assert all("clock_backward_jump" in entry["message"] for entry in entries)


def test_reset_clears_state_so_the_next_poll_starts_a_fresh_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(tmp_path)
    _patch_clock(monkeypatch, [0.0, 0.05])
    window._check_playback_clock(1.0)
    window._check_playback_clock(1.05)

    window._reset_playback_clock_diagnostics()

    assert window._last_clock_sample is None
    assert window._active_clock_anomaly_code is None
