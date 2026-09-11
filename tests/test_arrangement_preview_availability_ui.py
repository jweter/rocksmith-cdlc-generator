"""Regression coverage for issue #563.

A score-only project (no registered complete score / no arrangement draft) made
the Arrangement Preview tab's "Synchronized fretboard" and "Current review item"
panels render their full-height controls (a 190px fretboard canvas, string/fret
spinboxes, an always-disabled Accept Position button) even though none of it can
ever be actionable without an arrangement draft. That inflates the tab well past
what issue #454's scrollable-tab fix can make comfortable to navigate.

These tests exercise the real ``ArrangementPreviewSongWorkspaceWindow.
_build_arrangement_preview`` and ``_update_arrangement_preview_availability``
source directly against lightweight recording stand-ins for the ``tkinter``/
``ttk`` widget classes, following this repository's established no-live-display
convention (see ``tests/test_arrangement_preview_scroll_ui.py``).
"""

from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator import arrangement_preview_ui
from rocksmith_cdlc_generator.arrangement_preview_ui import ArrangementPreviewSongWorkspaceWindow


class _FakeVar:
    def __init__(self, value: object = "") -> None:
        self._value = value

    def get(self) -> object:
        return self._value

    def set(self, value: object) -> None:
        self._value = value


class _FakeWidget:
    def __init__(self, master=None, **kwargs: object) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children: list["_FakeWidget"] = []
        self.packed = False
        self.pack_calls: list[dict] = []
        if master is not None and hasattr(master, "children"):
            master.children.append(self)

    def pack(self, **kwargs: object) -> None:
        self.packed = True
        self.pack_calls.append(kwargs)

    def pack_forget(self) -> None:
        self.packed = False

    def bind(self, *_args: object, **_kwargs: object) -> None:
        return None

    def configure(self, **kwargs: object) -> None:
        self.kwargs.update(kwargs)

    def add(self, *_args: object, **_kwargs: object) -> None:
        return None


def _build(monkeypatch) -> SimpleNamespace:
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.ttk, "LabelFrame", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Panedwindow", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Label", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Button", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Combobox", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Spinbox", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.tk, "Canvas", _FakeWidget)
    monkeypatch.setattr(arrangement_preview_ui.tk, "StringVar", _FakeVar)

    window = SimpleNamespace(
        arrangement_preview_tab=_FakeWidget(),
        score_preview=None,
        _move_review=lambda delta: None,
        _change_zoom=lambda factor, focus_time=None: None,
        _arrangement_clicked=lambda event: None,
        _accept_reviewed_position=lambda: None,
        _draw_fretboard=lambda: None,
    )
    window._update_arrangement_preview_availability = (
        lambda: ArrangementPreviewSongWorkspaceWindow._update_arrangement_preview_availability(window)
    )
    ArrangementPreviewSongWorkspaceWindow._build_arrangement_preview(window)
    return window


def test_fretboard_and_position_controls_start_collapsed_with_no_arrangement_draft(monkeypatch) -> None:
    window = _build(monkeypatch)

    assert window.score_preview is None
    assert window.fretboard_content_frame.packed is False
    assert window.fretboard_unavailable_label.packed is True
    assert window.position_review_frame.packed is False
    assert window.position_review_unavailable_label.packed is True


def test_controls_expand_once_an_arrangement_draft_is_available(monkeypatch) -> None:
    window = _build(monkeypatch)

    window.score_preview = object()
    ArrangementPreviewSongWorkspaceWindow._update_arrangement_preview_availability(window)

    assert window.fretboard_content_frame.packed is True
    assert window.fretboard_unavailable_label.packed is False
    assert window.position_review_frame.packed is True
    assert window.position_review_unavailable_label.packed is False


def test_controls_recollapse_when_the_arrangement_draft_disappears_again(monkeypatch) -> None:
    window = _build(monkeypatch)
    window.score_preview = object()
    ArrangementPreviewSongWorkspaceWindow._update_arrangement_preview_availability(window)

    window.score_preview = None
    ArrangementPreviewSongWorkspaceWindow._update_arrangement_preview_availability(window)

    assert window.fretboard_content_frame.packed is False
    assert window.fretboard_unavailable_label.packed is True
    assert window.position_review_frame.packed is False
    assert window.position_review_unavailable_label.packed is True


def test_fret_box_and_detail_box_never_receive_a_third_reordering_child(monkeypatch) -> None:
    """Only the content/unavailable-label pair may live in fret_box's and
    detail_box's packing order; a third sibling would let a later pack_forget()/
    pack() cycle silently reorder content relative to it (see the construction
    comment in ``_build_arrangement_preview``)."""

    window = _build(monkeypatch)

    fret_box = window.fretboard_content_frame.master
    assert fret_box is window.fretboard_unavailable_label.master
    assert {child for child in fret_box.children} == {
        window.fretboard_content_frame,
        window.fretboard_unavailable_label,
    }

    detail_box = window.position_review_frame.master
    assert detail_box is window.position_review_unavailable_label.master
    non_position_children = {
        child
        for child in detail_box.children
        if child not in (window.position_review_frame, window.position_review_unavailable_label)
    }
    # Any such sibling (e.g. the "Review-required events…" label) is packed once,
    # unconditionally, and never toggled, so it cannot be reordered.
    for child in non_position_children:
        assert child.packed is True
