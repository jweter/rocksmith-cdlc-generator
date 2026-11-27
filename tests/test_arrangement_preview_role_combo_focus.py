"""Regression coverage for issue #796 slice 42 (Shared clock three-role switch).

A readonly ``ttk.Combobox`` keeps keyboard focus after the user picks a value.
``TimingReviewSongWorkspaceWindow`` binds ``<space>`` on the workspace window itself
to play/pause, but that window-level binding only fires when no descendant widget
currently holds focus. Before this fix, switching the Bass/Lead/Rhythm role combobox
left focus sitting on the combobox, so the very next ``<space>`` (or any other
combobox-intercepted key) never reached playback -- a stale-focus regression the
switch must never retain.

These tests exercise the real ``ArrangementPreviewSongWorkspaceWindow.
_fretboard_role_combo_selected``/``_release_role_combo_focus`` and
``EOFMeasureReviewMixin._eof_live_role_changed`` directly against lightweight
recording stand-ins, following this repository's established no-live-display
convention (see ``tests/test_arrangement_preview_availability_ui.py``).
"""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

from rocksmith_cdlc_generator import eof_measure_review_ui
from rocksmith_cdlc_generator.arrangement_preview_ui import ArrangementPreviewSongWorkspaceWindow


class _FakeCombo:
    def __init__(self, *, raise_on_selection_clear: bool = False) -> None:
        self.selection_clear_calls = 0
        self._raise_on_selection_clear = raise_on_selection_clear

    def selection_clear(self) -> None:
        self.selection_clear_calls += 1
        if self._raise_on_selection_clear:
            raise tk.TclError("no selection")


def _window(**extra: object) -> SimpleNamespace:
    window = SimpleNamespace(
        fretboard_role_combo=_FakeCombo(),
        _draw_fretboard_calls=0,
        focus_set_calls=0,
    )
    window._draw_fretboard = lambda: setattr(window, "_draw_fretboard_calls", window._draw_fretboard_calls + 1)
    window.focus_set = lambda: setattr(window, "focus_set_calls", window.focus_set_calls + 1)
    window._release_role_combo_focus = lambda: ArrangementPreviewSongWorkspaceWindow._release_role_combo_focus(window)
    for key, value in extra.items():
        setattr(window, key, value)
    return window


def test_role_combo_selection_redraws_and_releases_focus() -> None:
    window = _window()

    ArrangementPreviewSongWorkspaceWindow._fretboard_role_combo_selected(window)

    assert window._draw_fretboard_calls == 1
    assert window.fretboard_role_combo.selection_clear_calls == 1
    assert window.focus_set_calls == 1


def test_release_role_combo_focus_clears_both_synchronized_combos() -> None:
    window = _window(eof_live_role_combo=_FakeCombo())

    ArrangementPreviewSongWorkspaceWindow._release_role_combo_focus(window)

    assert window.fretboard_role_combo.selection_clear_calls == 1
    assert window.eof_live_role_combo.selection_clear_calls == 1
    assert window.focus_set_calls == 1


def test_release_role_combo_focus_tolerates_a_missing_eof_combo() -> None:
    """Arrangement Preview alone (without ``EOFMeasureReviewMixin`` mixed in) has no
    ``eof_live_role_combo``; the base window must still release its own focus."""
    window = _window()
    assert not hasattr(window, "eof_live_role_combo")

    ArrangementPreviewSongWorkspaceWindow._release_role_combo_focus(window)

    assert window.fretboard_role_combo.selection_clear_calls == 1
    assert window.focus_set_calls == 1


def test_release_role_combo_focus_swallows_tcl_error_from_a_destroyed_combo() -> None:
    """A combo torn down mid-callback (e.g. the window closing) must not raise out of
    the focus-release path; focus still gets returned to the window."""
    window = _window(fretboard_role_combo=_FakeCombo(raise_on_selection_clear=True))

    ArrangementPreviewSongWorkspaceWindow._release_role_combo_focus(window)

    assert window.fretboard_role_combo.selection_clear_calls == 1
    assert window.focus_set_calls == 1


def test_focus_set_error_does_not_propagate() -> None:
    window = _window()

    def _raise() -> None:
        raise tk.TclError("window is being destroyed")

    window.focus_set = _raise

    ArrangementPreviewSongWorkspaceWindow._release_role_combo_focus(window)

    assert window.fretboard_role_combo.selection_clear_calls == 1


def test_eof_live_role_changed_also_releases_focus() -> None:
    """``EOFMeasureReviewMixin``'s own combobox handler (bound directly on
    ``eof_live_role_combo``, and via ``add="+"`` onto ``fretboard_role_combo``) must
    release focus too, not only ``ArrangementPreviewSongWorkspaceWindow``'s handler."""
    role_var = SimpleNamespace(get=lambda: "bass", set=lambda _value: None)
    release_calls = 0

    def _release() -> None:
        nonlocal release_calls
        release_calls += 1

    window = SimpleNamespace(
        fretboard_role_var=role_var,
        _draw_fretboard=lambda: None,
        _refresh_eof_live_preview=lambda: None,
        _release_role_combo_focus=_release,
    )

    eof_measure_review_ui.EOFMeasureReviewMixin._eof_live_role_changed(window)

    assert release_calls == 1


def test_eof_live_role_changed_tolerates_a_window_without_the_release_hook() -> None:
    """A harness/composition that never mixes in ``ArrangementPreviewSongWorkspaceWindow``
    simply has no ``_release_role_combo_focus``; the handler must not require it."""
    role_var = SimpleNamespace(get=lambda: "rhythm", set=lambda _value: None)
    window = SimpleNamespace(
        fretboard_role_var=role_var,
        _draw_fretboard=lambda: None,
        _refresh_eof_live_preview=lambda: None,
    )
    assert not hasattr(window, "_release_role_combo_focus")

    eof_measure_review_ui.EOFMeasureReviewMixin._eof_live_role_changed(window)
