"""Regression coverage for issue #454.

The Arrangement Preview tab's content (score/fretboard controls, the live
TAB/highway canvases, and the official TAB reference viewer) is built by
several mixins that each pack their own widgets straight into
``self.arrangement_preview_tab``, one below another. On a laptop-resolution
window with Windows display scaling, that combined content routinely exceeds
the visible notebook height with no way to reach the rest of the page --
individual nested scrollbars (for example the official TAB image canvas'
own) cannot reach content packed *outside* themselves.

These tests exercise the real ``ArrangementPreviewSongWorkspaceWindow.
_build_scrollable_arrangement_preview_tab`` source directly against
lightweight recording stand-ins for the ``tkinter``/``ttk`` widget classes it
constructs, following this repository's established no-live-display
convention for GUI layout tests (see ``tests/test_desktop_score_tab_layout.py``
for the same approach applied to the Score & Mappings tab's analogous #304
off-screen-controls defect).
"""

from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator import arrangement_preview_ui
from rocksmith_cdlc_generator.arrangement_preview_ui import (
    ArrangementPreviewSongWorkspaceWindow,
    mousewheel_scroll_units,
)


class _FakeWidget:
    """Records construction args/children/bindings without needing a real Tk root."""

    def __init__(self, master=None, **kwargs: object) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children: list["_FakeWidget"] = []
        self.calls: list[tuple[str, tuple, dict]] = []
        self.bindings: dict[str, object] = {}
        if master is not None and hasattr(master, "children"):
            master.children.append(self)

    def bind(self, sequence: str, func: object) -> None:
        self.bindings[sequence] = func
        self.calls.append(("bind", (sequence, func), {}))

    def pack(self, **kwargs: object) -> None:
        self.calls.append(("pack", (), kwargs))

    def grid(self, **kwargs: object) -> None:
        self.calls.append(("grid", (), kwargs))

    def rowconfigure(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("rowconfigure", args, kwargs))

    def columnconfigure(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("columnconfigure", args, kwargs))

    def configure(self, **kwargs: object) -> None:
        self.calls.append(("configure", (), kwargs))
        self.kwargs.update(kwargs)


class _FakeFrame(_FakeWidget):
    pass


class _FakeScrollbar(_FakeWidget):
    def set(self, *args: object) -> None:  # pragma: no cover - trivial stand-in
        return None


class _FakeCanvas(_FakeWidget):
    def __init__(self, master=None, **kwargs: object) -> None:
        super().__init__(master, **kwargs)
        self.windows: list[tuple[tuple, dict]] = []
        self.itemconfigure_calls: list[tuple[object, dict]] = []
        self.yview_scroll_calls: list[tuple[int, str]] = []
        self.bind_all_calls: list[str] = []
        self.unbind_all_calls: list[str] = []
        self.scrollregion: object = None
        self._next_item_id = 1

    def create_window(self, *args: object, **kwargs: object) -> int:
        item_id = self._next_item_id
        self._next_item_id += 1
        self.windows.append((args, kwargs))
        return item_id

    def itemconfigure(self, item: object, **kwargs: object) -> None:
        self.itemconfigure_calls.append((item, kwargs))

    def yview(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("yview", args, kwargs))

    def yview_scroll(self, number: int, what: str) -> None:
        self.yview_scroll_calls.append((number, what))

    def bind_all(self, sequence: str, func: object) -> None:
        self.bind_all_calls.append(sequence)
        self.bindings[f"all:{sequence}"] = func

    def unbind_all(self, sequence: str) -> None:
        self.unbind_all_calls.append(sequence)

    def bbox(self, *_args: object) -> tuple[int, int, int, int]:
        return (0, 0, 640, 2200)

    def configure(self, **kwargs: object) -> None:
        super().configure(**kwargs)
        if "scrollregion" in kwargs:
            self.scrollregion = kwargs["scrollregion"]


class _FakeNotebook:
    def __init__(self) -> None:
        self.added: list[tuple[object, dict]] = []

    def add(self, widget: object, **kwargs: object) -> None:
        self.added.append((widget, kwargs))


def _build(monkeypatch) -> SimpleNamespace:
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(arrangement_preview_ui.ttk, "Scrollbar", _FakeScrollbar)
    monkeypatch.setattr(arrangement_preview_ui.tk, "Canvas", _FakeCanvas)

    window = SimpleNamespace(notebook=_FakeNotebook())
    ArrangementPreviewSongWorkspaceWindow._build_scrollable_arrangement_preview_tab(window)
    return window


def test_tab_is_added_once_wrapped_in_a_canvas_and_vertical_scrollbar(monkeypatch) -> None:
    window = _build(monkeypatch)

    assert len(window.notebook.added) == 1
    container, add_kwargs = window.notebook.added[0]
    assert add_kwargs.get("text") == "Arrangement Preview"
    assert isinstance(container, _FakeFrame)

    canvas = next(child for child in container.children if isinstance(child, _FakeCanvas))
    scrollbar = next(child for child in container.children if isinstance(child, _FakeScrollbar))
    assert scrollbar.kwargs.get("orient") == "vertical"
    assert scrollbar.kwargs.get("command") == canvas.yview

    configure_calls = [call for call in canvas.calls if call[0] == "configure"]
    assert any(call[2].get("yscrollcommand") == scrollbar.set for call in configure_calls)
    assert window.arrangement_preview_scroll_canvas is canvas


def test_content_frame_keeps_its_name_so_every_mixin_is_unaffected(monkeypatch) -> None:
    """Every ``_build_arrangement_preview`` mixin override packs into
    ``self.arrangement_preview_tab`` unaware it now lives inside a scroll region."""

    window = _build(monkeypatch)

    canvas = window.arrangement_preview_scroll_canvas
    content = window.arrangement_preview_tab
    assert isinstance(content, _FakeFrame)
    assert content.master is canvas
    assert content.kwargs.get("padding") == 12
    assert canvas.windows, "the content frame must be embedded via create_window"


def test_content_growth_expands_the_scrollregion_to_cover_full_content(monkeypatch) -> None:
    window = _build(monkeypatch)
    canvas = window.arrangement_preview_scroll_canvas
    content = window.arrangement_preview_tab

    assert "<Configure>" in content.bindings
    content.bindings["<Configure>"](SimpleNamespace())

    assert canvas.scrollregion == canvas.bbox()


def test_canvas_resize_pins_content_width_to_the_new_viewport_width(monkeypatch) -> None:
    """Resizing/maximizing/restoring the main window recomputes the scrollable
    region correctly by keeping the embedded content frame's width pinned to the
    canvas viewport (#454 requirement 6); only height should ever need scrolling."""

    window = _build(monkeypatch)
    canvas = window.arrangement_preview_scroll_canvas

    assert "<Configure>" in canvas.bindings
    canvas.bindings["<Configure>"](SimpleNamespace(width=734))

    item, kwargs = canvas.itemconfigure_calls[-1]
    assert kwargs.get("width") == 734


def test_mousewheel_only_scrolls_this_tab_while_the_pointer_is_over_it(monkeypatch) -> None:
    """Mouse wheel scrolls the full page while hovered (#454 requirement 3), and the
    global binding is released on <Leave> so it cannot steal wheel events destined for
    another tab, a dialog, or a nested canvas such as the official TAB viewer's own
    scrollable area (#454 requirement 4: nested scrolling must keep working)."""

    window = _build(monkeypatch)
    canvas = window.arrangement_preview_scroll_canvas

    assert canvas.bind_all_calls == []
    canvas.bindings["<Enter>"](SimpleNamespace())
    assert "<MouseWheel>" in canvas.bind_all_calls

    wheel_handler = canvas.bindings["all:<MouseWheel>"]
    wheel_handler(SimpleNamespace(delta=-120))
    assert canvas.yview_scroll_calls[-1] == (1, "units")
    wheel_handler(SimpleNamespace(delta=120))
    assert canvas.yview_scroll_calls[-1] == (-1, "units")

    canvas.bindings["<Leave>"](SimpleNamespace())
    assert "<MouseWheel>" in canvas.unbind_all_calls


def test_mousewheel_scroll_units_matches_windows_notch_convention() -> None:
    assert mousewheel_scroll_units(120) == -1
    assert mousewheel_scroll_units(-120) == 1
    assert mousewheel_scroll_units(240) == -2
    assert mousewheel_scroll_units(-240) == 2
    assert mousewheel_scroll_units(0) == 0


def test_mousewheel_scroll_units_small_delta_still_moves_one_unit() -> None:
    # Some trackpads/synthetic events deliver deltas smaller than a full 120 notch;
    # the direction must still be honored rather than rounding away to no movement.
    assert mousewheel_scroll_units(40) == -1
    assert mousewheel_scroll_units(-40) == 1
