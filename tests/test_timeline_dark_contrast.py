from __future__ import annotations

import inspect
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

from rocksmith_cdlc_generator.desktop_theme import PALETTE
from rocksmith_cdlc_generator.song_workspace_playback_ui import (
    PlaybackSongWorkspaceWindow,
    _ThemedTimelineCanvas,
)
from rocksmith_cdlc_generator.timing_review_ui import TimingReviewSongWorkspaceWindow


class FakeCanvas:
    """Headless canvas that mirrors the production Timeline fallback palette."""

    def __init__(self) -> None:
        self.lines: list[dict[str, object]] = []
        self.texts: list[dict[str, object]] = []
        self.ovals: list[dict[str, object]] = []
        self.rectangles: list[dict[str, object]] = []

    def delete(self, _tag: str) -> None:
        return None

    def winfo_width(self) -> int:
        return 900

    def winfo_height(self) -> int:
        return 430

    def create_line(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("fill", PALETTE.border_strong)
        self.lines.append(dict(kwargs))

    def create_text(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("fill", PALETTE.text)
        self.texts.append(dict(kwargs))

    def create_oval(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("fill", PALETTE.accent_hover)
        kwargs.setdefault("outline", PALETTE.accent_hover)
        self.ovals.append(dict(kwargs))

    def create_rectangle(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("fill", PALETTE.surface)
        kwargs.setdefault("outline", PALETTE.border)
        self.rectangles.append(dict(kwargs))


def _base_snapshot() -> SimpleNamespace:
    return SimpleNamespace(
        duration_seconds=10.0,
        timeline=SimpleNamespace(
            beat_times=[1.0, 2.0, 3.0],
            shared_anchor_audio_times=[2.0],
        ),
        review_queue=[
            SimpleNamespace(time_seconds=4.0, severity="FAIL"),
            SimpleNamespace(time_seconds=5.0, severity="WARNING"),
        ],
    )


def _waveform() -> SimpleNamespace:
    return SimpleNamespace(
        bucket_count=2,
        bucket_frames=1,
        sample_rate_hz=1.0,
        minimums=[-0.5, -0.25],
        maximums=[0.5, 0.25],
    )


def test_themed_canvas_defaults_missing_primitive_colors_without_overriding_explicit_fill() -> None:
    canvas = object.__new__(_ThemedTimelineCanvas)

    with patch.object(tk.Canvas, "create_text", return_value=1) as create_text:
        canvas.create_text(0, 0, text="overlay")
        assert create_text.call_args.kwargs["fill"] == PALETTE.text

    with patch.object(tk.Canvas, "create_line", return_value=2) as create_line:
        canvas.create_line(0, 0, 1, 1)
        assert create_line.call_args.kwargs["fill"] == PALETTE.border_strong
        canvas.create_line(0, 0, 1, 1, fill=PALETTE.danger)
        assert create_line.call_args.kwargs["fill"] == PALETTE.danger

    with patch.object(tk.Canvas, "create_oval", return_value=3) as create_oval:
        canvas.create_oval(0, 0, 1, 1)
        assert create_oval.call_args.kwargs["fill"] == PALETTE.accent_hover
        assert create_oval.call_args.kwargs["outline"] == PALETTE.accent_hover

    with patch.object(tk.Canvas, "create_rectangle", return_value=4) as create_rectangle:
        canvas.create_rectangle(0, 0, 1, 1, outline="")
        assert create_rectangle.call_args.kwargs["fill"] == PALETTE.surface
        assert create_rectangle.call_args.kwargs["outline"] == ""


def test_timeline_build_uses_themed_canvas_for_inherited_review_overlays() -> None:
    assert issubclass(TimingReviewSongWorkspaceWindow, PlaybackSongWorkspaceWindow)
    assert "_ThemedTimelineCanvas(" in inspect.getsource(PlaybackSongWorkspaceWindow._build_timeline)


def test_timeline_drawables_use_explicit_dark_theme_contrast() -> None:
    window = PlaybackSongWorkspaceWindow.__new__(PlaybackSongWorkspaceWindow)
    canvas = FakeCanvas()
    window.timeline_canvas = canvas
    window.snapshot = _base_snapshot()
    window.waveform = _waveform()
    window._view_start = 0.0
    window._zoom = 1.0
    window._selected_time = 6.0

    window._draw_timeline()

    assert canvas.lines
    assert canvas.texts
    assert canvas.ovals
    assert all(call.get("fill") for call in canvas.lines)
    assert all(call.get("fill") for call in canvas.texts)
    assert all(call.get("fill") != "black" for call in canvas.lines + canvas.texts + canvas.ovals)
    assert any(call.get("fill") == PALETTE.info for call in canvas.lines)
    assert any(call.get("fill") == PALETTE.text for call in canvas.texts)
    assert any(call.get("fill") == PALETTE.text_muted for call in canvas.texts)
    assert any(call.get("fill") == PALETTE.danger for call in canvas.lines)
    assert any(call.get("fill") == PALETTE.warning for call in canvas.lines)
    assert canvas.ovals[0]["fill"] == PALETTE.accent_hover


def test_timing_review_final_draw_path_keeps_overlay_primitives_visible() -> None:
    window = TimingReviewSongWorkspaceWindow.__new__(TimingReviewSongWorkspaceWindow)
    canvas = FakeCanvas()
    window.timeline_canvas = canvas
    window.snapshot = _base_snapshot()
    window.waveform = _waveform()
    window._view_start = 0.0
    window._zoom = 1.0
    window._selected_time = 6.0
    window._loop_start = 0.5
    window._loop_end = 1.5
    window.reviewed_timing = SimpleNamespace(
        anchors=[SimpleNamespace(reviewed_time_seconds=2.0, locked=True)]
    )
    window.candidate_shared_timeline = SimpleNamespace(
        anchors=[SimpleNamespace(audio_time_seconds=3.0)]
    )
    window.score_timing_refit_preview = None
    window.score_timing_anchor_review = SimpleNamespace(
        anchors=[SimpleNamespace(recording_time_seconds=4.0)]
    )

    window._draw_timeline()

    assert canvas.rectangles
    overlay_text = {call.get("text") for call in canvas.texts}
    assert {"LOOP", "◆", "◇", "●"}.issubset(overlay_text)
    all_primitives = canvas.lines + canvas.texts + canvas.ovals + canvas.rectangles
    assert all(call.get("fill") not in {None, "", "black"} for call in all_primitives)
