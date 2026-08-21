from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator import timing_review_ui
from rocksmith_cdlc_generator.song_workspace_playback_ui import PlaybackSongWorkspaceWindow
from rocksmith_cdlc_generator.timing_review_ui import (
    CLICK_TRACK_LABEL,
    CLICK_TRACK_TOOLTIP,
    TimingReviewSongWorkspaceWindow,
)


class _FakeBooleanVar:
    def __init__(self, value: bool = False) -> None:
        self._value = value

    def get(self) -> bool:
        return self._value

    def set(self, value: bool) -> None:
        self._value = value


class _FakeFrame:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def pack(self, **kwargs) -> None:
        pass


class _FakeSeparator:
    def __init__(self, *args, **kwargs) -> None:
        self.kwargs = kwargs

    def pack(self, **kwargs) -> None:
        pass


class _FakeCheckbutton:
    def __init__(self, parent, *, text=None, variable=None, command=None) -> None:
        self.parent = parent
        self.text = text
        self.variable = variable
        self.command = command

    def pack(self, **kwargs) -> None:
        pass


def test_base_playback_window_transport_extra_hook_is_a_no_op() -> None:
    # The base hook must be safely callable with nothing wired up: subclasses that
    # do not override it (or the default window itself) add no transport controls.
    window = SimpleNamespace()

    PlaybackSongWorkspaceWindow._build_transport_extra(window, transport=_FakeFrame())


def test_build_transport_extra_places_click_track_in_the_transport_row(monkeypatch) -> None:
    super_calls: list[object] = []
    monkeypatch.setattr(
        PlaybackSongWorkspaceWindow,
        "_build_transport_extra",
        lambda self, transport: super_calls.append(transport),
    )
    monkeypatch.setattr(timing_review_ui.tk, "BooleanVar", _FakeBooleanVar)
    monkeypatch.setattr(timing_review_ui.ttk, "Separator", _FakeSeparator)
    monkeypatch.setattr(timing_review_ui.ttk, "Checkbutton", _FakeCheckbutton)
    captured_tooltips: list[tuple[object, str]] = []
    monkeypatch.setattr(
        timing_review_ui,
        "Tooltip",
        lambda widget, text: captured_tooltips.append((widget, text)),
    )

    # A bare instance (no __init__) so `self` is a genuine
    # TimingReviewSongWorkspaceWindow for the method's internal `super()` call to
    # resolve correctly, without constructing a real Tk window.
    window = TimingReviewSongWorkspaceWindow.__new__(TimingReviewSongWorkspaceWindow)
    window._set_click = lambda: None
    fake_transport = _FakeFrame()

    window._build_transport_extra(fake_transport)

    # The base hook still ran first, so any future base-level transport additions
    # keep working alongside this one.
    assert super_calls == [fake_transport]

    assert isinstance(window.click_var, _FakeBooleanVar)
    assert window.click_var.get() is False

    button = window.click_track_button
    assert isinstance(button, _FakeCheckbutton)
    assert button.parent is fake_transport
    assert button.text == CLICK_TRACK_LABEL
    assert button.variable is window.click_var
    assert button.command is window._set_click

    assert captured_tooltips == [(button, CLICK_TRACK_TOOLTIP)]


def test_click_track_label_and_tooltip_never_communicate_by_color_alone() -> None:
    # This control has no semantic-status color at all -- confirm the label and
    # tooltip text alone (not layout/color) carry its meaning, per the #305
    # "never color alone" principle applied to plain controls too.
    assert "Click Track" in CLICK_TRACK_LABEL
    assert "audible pulse" in CLICK_TRACK_TOOLTIP
    assert "beat grid" in CLICK_TRACK_TOOLTIP
