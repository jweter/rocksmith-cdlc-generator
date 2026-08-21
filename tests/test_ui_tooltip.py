from __future__ import annotations

from rocksmith_cdlc_generator import ui_tooltip
from rocksmith_cdlc_generator.ui_tooltip import Tooltip


class _FakeWidget:
    """Minimal stand-in for a tkinter widget exposing only what Tooltip uses."""

    def __init__(self) -> None:
        self.bindings: dict[str, list] = {}
        self.after_calls: list[tuple[int, object]] = []
        self.cancelled: list[str] = []
        self._exists = True
        self._next_after_id = 0
        self.rootx = 100
        self.rooty = 200
        self.height = 24

    def bind(self, sequence, func, add=None):
        self.bindings.setdefault(sequence, []).append(func)

    def after(self, ms, func):
        self._next_after_id += 1
        after_id = f"after#{self._next_after_id}"
        self.after_calls.append((ms, func))
        return after_id

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)

    def winfo_exists(self):
        return self._exists

    def winfo_rootx(self):
        return self.rootx

    def winfo_rooty(self):
        return self.rooty

    def winfo_height(self):
        return self.height


class _FakeLabel:
    def __init__(self, parent, **kwargs):
        self.parent = parent
        self.kwargs = kwargs

    def pack(self):
        pass


class _FakeToplevel:
    instances: list["_FakeToplevel"] = []

    def __init__(self, parent):
        self.parent = parent
        self.geometry: str | None = None
        self.destroyed = False
        self.attributes: dict[str, object] = {}
        _FakeToplevel.instances.append(self)

    def wm_overrideredirect(self, flag):
        self.overrideredirect_flag = flag

    def wm_attributes(self, name, value):
        self.attributes[name] = value

    def wm_geometry(self, spec):
        self.geometry = spec

    def destroy(self):
        self.destroyed = True


def _patch_tk_widgets(monkeypatch) -> None:
    _FakeToplevel.instances = []
    monkeypatch.setattr(ui_tooltip.tk, "Toplevel", _FakeToplevel)
    monkeypatch.setattr(ui_tooltip.ttk, "Label", _FakeLabel)


def test_default_delay_is_a_deliberate_hover_delay() -> None:
    # Long enough that a pointer sweeping across a toolbar does not flash popups;
    # short enough that a deliberate hover feels immediate.
    assert ui_tooltip.DEFAULT_DELAY_MS == 500


def test_init_binds_enter_leave_press_and_destroy_with_additive_add() -> None:
    widget = _FakeWidget()

    tip = Tooltip(widget, "hello")

    assert widget.bindings["<Enter>"] == [tip._schedule]
    assert widget.bindings["<Leave>"] == [tip._hide]
    assert widget.bindings["<ButtonPress>"] == [tip._hide]
    assert widget.bindings["<Destroy>"] == [tip._hide]


def test_schedule_cancels_previous_pending_before_rescheduling() -> None:
    widget = _FakeWidget()
    tip = Tooltip(widget, "hello", delay_ms=250)

    tip._schedule()
    assert widget.after_calls[-1] == (250, tip._show)
    assert widget.cancelled == []

    tip._schedule()
    assert widget.cancelled == ["after#1"]
    assert widget.after_calls[-1] == (250, tip._show)


def test_show_creates_popup_below_widget_with_wrapped_text(monkeypatch) -> None:
    _patch_tk_widgets(monkeypatch)
    widget = _FakeWidget()
    tip = Tooltip(widget, "explain me")

    tip._show()

    assert len(_FakeToplevel.instances) == 1
    popup = _FakeToplevel.instances[0]
    assert popup.geometry == "+112+230"  # rootx + 12, rooty + height + 6
    assert popup.overrideredirect_flag is True
    assert tip._popup is popup


def test_show_is_idempotent_while_popup_already_shown(monkeypatch) -> None:
    _patch_tk_widgets(monkeypatch)
    widget = _FakeWidget()
    tip = Tooltip(widget, "explain me")

    tip._show()
    tip._show()

    assert len(_FakeToplevel.instances) == 1


def test_show_does_nothing_once_widget_no_longer_exists(monkeypatch) -> None:
    _patch_tk_widgets(monkeypatch)
    widget = _FakeWidget()
    widget._exists = False
    tip = Tooltip(widget, "explain me")

    tip._show()

    assert _FakeToplevel.instances == []
    assert tip._popup is None


def test_hide_destroys_a_shown_popup() -> None:
    class _Popup:
        def __init__(self) -> None:
            self.destroyed = False

        def destroy(self) -> None:
            self.destroyed = True

    widget = _FakeWidget()
    tip = Tooltip(widget, "explain me")
    popup = _Popup()
    tip._popup = popup

    tip._hide()

    assert popup.destroyed is True
    assert tip._popup is None


def test_hide_cancels_a_still_pending_show_before_it_fires() -> None:
    widget = _FakeWidget()
    tip = Tooltip(widget, "explain me")
    tip._schedule()

    tip._hide()

    assert widget.cancelled == ["after#1"]
    assert tip._after_id is None


def test_hide_without_a_shown_popup_is_a_safe_no_op() -> None:
    widget = _FakeWidget()
    tip = Tooltip(widget, "explain me")

    tip._hide()

    assert tip._popup is None
