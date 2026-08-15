from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator.arrangement_edit_history_ui import (
    ArrangementEditHistorySongWorkspaceWindow,
)


class _Widget:
    def __init__(self, widget_class: str) -> None:
        self.widget_class = widget_class

    def winfo_class(self) -> str:
        return self.widget_class


def _event(keysym: str, *, widget_class: str = "Canvas", state: int = 0):
    return SimpleNamespace(
        keysym=keysym,
        widget=_Widget(widget_class),
        state=state,
    )


def _workspace():
    window = object.__new__(ArrangementEditHistorySongWorkspaceWindow)
    calls: list[tuple[str, float | None]] = []
    window._play_pause = lambda: calls.append(("toggle", None))
    window._seek_relative = lambda delta: calls.append(("relative", float(delta)))
    window._seek_to = lambda seconds: calls.append(("absolute", float(seconds)))
    window.snapshot = SimpleNamespace(duration_seconds=123.5)
    return window, calls


def test_transport_shortcut_dispatches_review_controls() -> None:
    window, calls = _workspace()

    assert window._transport_shortcut(_event("space")) == "break"
    assert window._transport_shortcut(_event("k")) == "break"
    assert window._transport_shortcut(_event("j")) == "break"
    assert window._transport_shortcut(_event("l")) == "break"
    assert window._transport_shortcut(_event("Home")) == "break"
    assert window._transport_shortcut(_event("End")) == "break"

    assert calls == [
        ("toggle", None),
        ("toggle", None),
        ("relative", -5.0),
        ("relative", 5.0),
        ("absolute", 0.0),
        ("absolute", 123.5),
    ]


def test_transport_shortcuts_do_not_steal_text_entry_or_modified_chords() -> None:
    window, calls = _workspace()

    assert window._transport_shortcut(_event("space", widget_class="TEntry")) is None
    assert window._transport_shortcut(_event("j", widget_class="Text")) is None
    assert window._transport_shortcut(_event("l", widget_class="TCombobox")) is None
    assert window._transport_shortcut(_event("k", state=0x0004)) is None
    assert window._transport_shortcut(_event("Home", state=0x0008)) is None

    assert calls == []


def test_end_shortcut_requires_loaded_workspace_snapshot() -> None:
    window, calls = _workspace()
    window.snapshot = None

    assert window._transport_shortcut(_event("End")) is None
    assert calls == []


def test_bind_transport_shortcuts_registers_only_expected_keys() -> None:
    window = object.__new__(ArrangementEditHistorySongWorkspaceWindow)
    bindings: list[tuple[str, object, str | None]] = []
    window.bind = lambda sequence, callback, add=None: bindings.append((sequence, callback, add))

    window._bind_transport_shortcuts()

    assert [sequence for sequence, _callback, _add in bindings] == [
        "<space>",
        "<KeyPress-k>",
        "<KeyPress-j>",
        "<KeyPress-l>",
        "<Home>",
        "<End>",
    ]
    assert all(add == "+" for _sequence, _callback, add in bindings)
