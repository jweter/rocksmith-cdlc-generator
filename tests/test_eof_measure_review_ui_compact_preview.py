"""Regression coverage for issue #563's live-preview collapse.

``EOFMeasureReviewMixin`` builds two Canvas widgets (~235px + ~255px, ~490px total)
for the "Live fingering preview" section at the top of every Song Workspace
Arrangement Preview tab. Product Reality testing on the score-only BWV1007 project
found that this section stays at full height even when no arrangement draft exists
yet -- both canvases render only a "No arrangement available" placeholder (or nothing
at all) but still consume the same ~490px of vertical space as when a real arrangement
is loaded, contributing directly to the "excessively long" page reported in #563.

These tests exercise the real ``_refresh_eof_live_preview``/``_set_eof_live_preview_compact``
logic against lightweight recording stand-ins for the tkinter/ttk widget classes,
following the no-display-server convention established in
``tests/test_official_tab_rotate_buttons_ui.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator import eof_measure_review_ui


class _FakeVar:
    def __init__(self, value: object = None, **_kwargs: object) -> None:
        self._value = value

    def get(self) -> object:
        return self._value

    def set(self, value: object) -> None:
        self._value = value

    def trace_add(self, *_args: object, **_kwargs: object) -> None:
        return None


class _FakeWidget:
    """Records construction args/children without needing a real Tk root."""

    def __init__(self, master: "_FakeWidget | None" = None, **kwargs: object) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children: list["_FakeWidget"] = []
        if master is not None:
            master.children.append(self)

    def winfo_children(self) -> list["_FakeWidget"]:
        return list(self.children)

    def cget(self, name: str) -> object:
        return self.kwargs.get(name)

    def configure(self, **kwargs: object) -> None:
        self.kwargs.update(kwargs)

    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def _record(*_args: object, **_kwargs: object):
            return None

        self.__dict__[name] = _record
        return _record


class _FakeFrame(_FakeWidget):
    pass


class _FakeLabel(_FakeWidget):
    pass


class _FakeButton(_FakeWidget):
    pass


class _FakeCombobox(_FakeWidget):
    pass


class _FakeCheckbutton(_FakeWidget):
    pass


class _FakeCanvas(_FakeWidget):
    pass


class _FakeBase:
    """Stand-in for the ancestor class supplying the shared arrangement-preview tab."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def set_project(self, project: object) -> None:
        pass

    def refresh(self) -> None:
        pass

    def _build_arrangement_preview(self) -> None:
        self.arrangement_preview_tab = _FakeFrame()
        self.arrangement_canvas = _FakeWidget()
        self.fretboard_role_var = _FakeVar("lead")


class _Harness(eof_measure_review_ui.EOFMeasureReviewMixin, _FakeBase):
    pass


def _build_harness(monkeypatch) -> _Harness:
    monkeypatch.setattr(eof_measure_review_ui.ttk, "LabelFrame", _FakeFrame)
    monkeypatch.setattr(eof_measure_review_ui.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(eof_measure_review_ui.ttk, "Label", _FakeLabel)
    monkeypatch.setattr(eof_measure_review_ui.ttk, "Button", _FakeButton)
    monkeypatch.setattr(eof_measure_review_ui.ttk, "Combobox", _FakeCombobox)
    monkeypatch.setattr(eof_measure_review_ui.ttk, "Checkbutton", _FakeCheckbutton)
    monkeypatch.setattr(eof_measure_review_ui.tk, "Canvas", _FakeCanvas)
    monkeypatch.setattr(eof_measure_review_ui.tk, "StringVar", _FakeVar)
    monkeypatch.setattr(eof_measure_review_ui.tk, "BooleanVar", _FakeVar)

    harness = _Harness()
    harness._build_arrangement_preview()
    # The draw pipeline needs a real Tk font/measure system for text metrics; the
    # behavior under test is the canvas height toggle, not pixel rendering.
    harness._draw_eof_tab = lambda: None
    harness._draw_eof_highway = lambda: None
    return harness


def _fake_arrangement(instrument: str = "lead"):
    return SimpleNamespace(instrument=instrument, notes=[], tuning_midi=[])


def test_canvases_start_at_full_height(monkeypatch) -> None:
    harness = _build_harness(monkeypatch)

    assert harness.eof_tab_canvas.kwargs["height"] == eof_measure_review_ui._TAB_CANVAS_HEIGHT
    assert harness.eof_highway_canvas.kwargs["height"] == eof_measure_review_ui._HIGHWAY_CANVAS_HEIGHT


def test_no_arrangement_draft_collapses_both_canvases(monkeypatch) -> None:
    harness = _build_harness(monkeypatch)
    harness.score_preview = None

    harness._refresh_eof_live_preview()

    assert harness.eof_tab_canvas.kwargs["height"] == eof_measure_review_ui._TAB_CANVAS_HEIGHT_COMPACT
    assert harness.eof_highway_canvas.kwargs["height"] == eof_measure_review_ui._HIGHWAY_CANVAS_HEIGHT_COMPACT


def test_no_matching_role_arrangement_also_collapses(monkeypatch) -> None:
    harness = _build_harness(monkeypatch)
    harness.fretboard_role_var.set("bass")
    harness.score_preview = SimpleNamespace(arrangements=[_fake_arrangement("lead")])

    harness._refresh_eof_live_preview()

    assert harness.eof_tab_canvas.kwargs["height"] == eof_measure_review_ui._TAB_CANVAS_HEIGHT_COMPACT
    assert harness.eof_highway_canvas.kwargs["height"] == eof_measure_review_ui._HIGHWAY_CANVAS_HEIGHT_COMPACT


def test_available_arrangement_restores_full_height(monkeypatch) -> None:
    harness = _build_harness(monkeypatch)
    harness.score_preview = None
    harness._refresh_eof_live_preview()
    assert harness.eof_tab_canvas.kwargs["height"] == eof_measure_review_ui._TAB_CANVAS_HEIGHT_COMPACT

    harness.score_preview = SimpleNamespace(arrangements=[_fake_arrangement("lead")])
    harness._refresh_eof_live_preview()

    assert harness.eof_tab_canvas.kwargs["height"] == eof_measure_review_ui._TAB_CANVAS_HEIGHT
    assert harness.eof_highway_canvas.kwargs["height"] == eof_measure_review_ui._HIGHWAY_CANVAS_HEIGHT


def test_compact_toggle_does_not_disturb_other_kwargs(monkeypatch) -> None:
    """Only ``height`` should change -- the canvas identity/pack order that
    OfficialTabReferenceMixin relies on to locate/swap these widgets must be untouched."""
    harness = _build_harness(monkeypatch)
    original_background = harness.eof_tab_canvas.kwargs["background"]

    harness.score_preview = None
    harness._refresh_eof_live_preview()

    assert harness.eof_tab_canvas.kwargs["background"] == original_background
    assert harness.eof_tab_canvas is harness.eof_tab_canvas
