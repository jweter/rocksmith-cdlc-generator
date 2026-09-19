"""Regression coverage for issue #563 (Arrangement Preview becomes excessively long).

``CollapsibleSection`` is the shared widget several Arrangement Preview panels
(event timing, techniques, chord fingering/identity, review queue summary,
multi-track composition, edit history) now use in place of a plain, always-expanded
``ttk.LabelFrame``. These tests exercise the real widget class against lightweight
recording stand-ins for ``ttk.Frame``/``ttk.Button``, following the no-display-server
convention established in ``tests/test_guided_desktop_next_action_layout.py``.
"""

from __future__ import annotations

from rocksmith_cdlc_generator import collapsible_section
from rocksmith_cdlc_generator.collapsible_section import (
    CollapsibleSection,
    collapsible_section_header_text,
)


def test_header_text_marks_expanded_state() -> None:
    assert collapsible_section_header_text("Human-reviewed techniques", expanded=True) == "▾ Human-reviewed techniques"


def test_header_text_marks_collapsed_state() -> None:
    assert collapsible_section_header_text("Human-reviewed techniques", expanded=False) == "▸ Human-reviewed techniques"


class _FakeWidget:
    """Records construction args/pack calls without needing a real Tk root."""

    def __init__(self, master=None, **kwargs: object) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children: list["_FakeWidget"] = []
        self.calls: list[tuple[str, tuple, dict]] = []
        if master is not None and hasattr(master, "children"):
            master.children.append(self)

    def pack(self, **kwargs: object) -> None:
        self.calls.append(("pack", (), kwargs))

    def pack_forget(self) -> None:
        self.calls.append(("pack_forget", (), {}))

    def configure(self, **kwargs: object) -> None:
        self.kwargs.update(kwargs)
        self.calls.append(("configure", (), kwargs))

    def winfo_children(self) -> list["_FakeWidget"]:
        return list(self.children)


class _FakeButton(_FakeWidget):
    pass


class _FakeFrame(_FakeWidget):
    pass


def _patch_widgets(monkeypatch) -> None:
    monkeypatch.setattr(collapsible_section.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(collapsible_section.ttk, "Button", _FakeButton)


def _is_packed(widget: _FakeWidget) -> bool:
    for name, _args, _kwargs in reversed(widget.calls):
        if name == "pack":
            return True
        if name == "pack_forget":
            return False
    return False


def test_defaults_to_expanded_and_packs_the_body(monkeypatch) -> None:
    _patch_widgets(monkeypatch)
    section = CollapsibleSection(None, text="Human-reviewed techniques")

    assert section.expanded is True
    assert isinstance(section.body, _FakeFrame)
    assert _is_packed(section.body)
    assert section.toggle_button.kwargs["text"] == "▾ Human-reviewed techniques"


def test_can_start_collapsed(monkeypatch) -> None:
    _patch_widgets(monkeypatch)
    section = CollapsibleSection(None, text="Human-reviewed techniques", expanded=False)

    assert section.expanded is False
    assert not _is_packed(section.body)
    assert section.toggle_button.kwargs["text"] == "▸ Human-reviewed techniques"


def test_toggle_collapses_an_expanded_section(monkeypatch) -> None:
    _patch_widgets(monkeypatch)
    section = CollapsibleSection(None, text="Human-reviewed techniques")

    section.toggle()

    assert section.expanded is False
    assert not _is_packed(section.body)
    assert section.toggle_button.kwargs["text"] == "▸ Human-reviewed techniques"


def test_toggle_expands_a_collapsed_section(monkeypatch) -> None:
    _patch_widgets(monkeypatch)
    section = CollapsibleSection(None, text="Human-reviewed techniques", expanded=False)

    section.toggle()

    assert section.expanded is True
    assert _is_packed(section.body)
    assert section.toggle_button.kwargs["text"] == "▾ Human-reviewed techniques"


def test_toggle_button_command_is_wired_to_toggle(monkeypatch) -> None:
    """The header must actually be clickable, not merely inert decoration."""

    _patch_widgets(monkeypatch)
    section = CollapsibleSection(None, text="Human-reviewed techniques")

    section.toggle_button.kwargs["command"]()

    assert section.expanded is False
    assert not _is_packed(section.body)


def test_body_uses_requested_padding(monkeypatch) -> None:
    _patch_widgets(monkeypatch)
    section = CollapsibleSection(None, text="Human-reviewed techniques", padding=12)

    assert section.body.kwargs["padding"] == 12
