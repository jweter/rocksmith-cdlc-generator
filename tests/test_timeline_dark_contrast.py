from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator.desktop_theme import PALETTE
from rocksmith_cdlc_generator.song_workspace_playback_ui import PlaybackSongWorkspaceWindow


class FakeCanvas:
    def __init__(self) -> None:
        self.lines: list[dict[str, object]] = []
        self.texts: list[dict[str, object]] = []
        self.ovals: list[dict[str, object]] = []

    def delete(self, _tag: str) -> None:
        return None

    def winfo_width(self) -> int:
        return 900

    def winfo_height(self) -> int:
        return 430

    def create_line(self, *args: object, **kwargs: object) -> None:
        self.lines.append(dict(kwargs))

    def create_text(self, *args: object, **kwargs: object) -> None:
        self.texts.append(dict(kwargs))

    def create_oval(self, *args: object, **kwargs: object) -> None:
        self.ovals.append(dict(kwargs))


def test_timeline_drawables_use_explicit_dark_theme_contrast() -> None:
    window = PlaybackSongWorkspaceWindow.__new__(PlaybackSongWorkspaceWindow)
    canvas = FakeCanvas()
    window.timeline_canvas = canvas
    window.snapshot = SimpleNamespace(
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
    window.waveform = SimpleNamespace(
        bucket_count=2,
        bucket_frames=1,
        sample_rate_hz=1.0,
        minimums=[-0.5, -0.25],
        maximums=[0.5, 0.25],
    )
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
