"""Regression coverage for Product Reality issue #305 (redundant next-action callout).

`DesktopApp._build_layout` builds a "Next action" `LabelFrame` callout that is
blank until a project is refreshed. `GuidedDesktopApp` (the base of the
shipped `cdlc-desktop` shell, via `LiveDiagnosticsGuidedDesktopApp`) stacks
its own, friendlier "Song progress" panel directly above that same callout,
deriving both from the identical underlying
`build_multi_arrangement_workflow_plan` result. Before this fix, that left a
blank box under the guided panel before any project was open, and a
raw/duplicate developer-facing next-step string under it afterward -- exactly
the "reduce developer-facing/raw-state presentation" and "make stale/invalid
[...] visually unmistakable" empty/redundant-state clutter #305 asks the
guided shell to avoid.

These tests exercise the real `_build_layout` methods against lightweight
recording stand-ins for the `tkinter`/`ttk` widget and variable classes they
construct, following the no-display-server convention established in
`tests/test_desktop_score_tab_layout.py`.
"""

from __future__ import annotations

from rocksmith_cdlc_generator import desktop_app, desktop_shell, guided_desktop
from rocksmith_cdlc_generator.score_source import ArrangementRole


class _FakeVar:
    def __init__(self, value=None, **kwargs) -> None:
        self._value = value if value is not None else kwargs.get("value")

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _FakeWidget:
    """Records construction args/children/calls without needing a real Tk root."""

    def __init__(self, master=None, **kwargs: object) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children: list["_FakeWidget"] = []
        self.calls: list[tuple[str, tuple, dict]] = []
        if master is not None and hasattr(master, "children"):
            master.children.append(self)

    def winfo_children(self) -> list["_FakeWidget"]:
        return list(self.children)

    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def _record(*args: object, **kwargs: object):
            self.calls.append((name, args, kwargs))
            return None

        self.__dict__[name] = _record
        return _record


class _FakeFrame(_FakeWidget):
    pass


class _FakeLabelFrame(_FakeWidget):
    pass


class _FakeLabel(_FakeWidget):
    pass


class _FakeButton(_FakeWidget):
    pass


class _FakeEntry(_FakeWidget):
    pass


class _FakeCombobox(_FakeWidget):
    pass


class _FakeTreeview(_FakeWidget):
    pass


class _FakeNotebook(_FakeWidget):
    pass


class _FakeScrollbar(_FakeWidget):
    pass


class _FakeText(_FakeWidget):
    pass


class _FakeProgressbar(_FakeWidget):
    pass


def _patch_widgets(monkeypatch) -> None:
    # `ttk`/`tk` are the same shared `tkinter.ttk`/`tkinter` module objects in
    # desktop_app, desktop_shell, and guided_desktop (each does
    # `from tkinter import ttk` / `import tkinter as tk`), so patching once
    # applies across all three modules' `_build_layout` chain.
    monkeypatch.setattr(desktop_app.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(desktop_app.ttk, "LabelFrame", _FakeLabelFrame)
    monkeypatch.setattr(desktop_app.ttk, "Label", _FakeLabel)
    monkeypatch.setattr(desktop_app.ttk, "Button", _FakeButton)
    monkeypatch.setattr(desktop_app.ttk, "Entry", _FakeEntry)
    monkeypatch.setattr(desktop_app.ttk, "Combobox", _FakeCombobox)
    monkeypatch.setattr(desktop_app.ttk, "Treeview", _FakeTreeview)
    monkeypatch.setattr(desktop_app.ttk, "Notebook", _FakeNotebook)
    monkeypatch.setattr(desktop_app.ttk, "Scrollbar", _FakeScrollbar)
    monkeypatch.setattr(desktop_app.ttk, "Progressbar", _FakeProgressbar)
    monkeypatch.setattr(desktop_app.tk, "Text", _FakeText)
    monkeypatch.setattr(desktop_app.tk, "StringVar", _FakeVar)
    monkeypatch.setattr(desktop_app.tk, "DoubleVar", _FakeVar)


class _FakeGuidedApp(guided_desktop.GuidedDesktopApp):
    """A real `GuidedDesktopApp` whose `__init__` never touches a Tk root.

    Subclassing (rather than calling the layout methods unbound, as
    `test_desktop_score_tab_layout.py` does for the single-class
    `DesktopApp`) is required here because `GuidedDesktopApp._build_layout`
    and `ProductDesktopApp._build_layout` each call zero-arg `super()`, which
    needs `self` to be a real instance of the defining class's subtree to
    resolve the MRO.
    """

    def __init__(self) -> None:  # noqa: super-init-not-called -- intentional Tk bypass
        self.children: list[_FakeWidget] = []
        self.song_var = _FakeVar()
        self.project_var = _FakeVar()
        self.next_action_var = _FakeVar()
        self.status_var = _FakeVar()
        self.score_var = _FakeVar()
        self.rights_note_var = _FakeVar()
        self.rights_source_var = _FakeVar()
        self.rights_class_var = _FakeVar()
        self.mapping_vars = {role: _FakeVar() for role in ArrangementRole}
        self.mapping_status_vars = {role: _FakeVar() for role in ArrangementRole}
        self.new_project_dialog = lambda: None
        self.open_project_dialog = lambda: None
        self.run_automatic_steps = lambda: None
        self.refresh_project = lambda: None
        self.register_score_dialog = lambda: None
        self.record_rights_review = lambda: None
        self.open_song_workspace = lambda: None
        self._build_layout()

    def winfo_children(self) -> list[_FakeWidget]:
        return list(self.children)


def test_guided_shell_hides_the_redundant_base_next_action_callout(monkeypatch) -> None:
    """GuidedDesktopApp must not leave the base raw "Next action" callout
    visible: its own "Song progress" panel already presents the identical
    next-step information, so a second, blank-until-refresh or duplicate
    developer-facing box directly beneath it is empty/redundant-state
    clutter (#305), not an additional useful surface."""

    _patch_widgets(monkeypatch)
    app = _FakeGuidedApp()

    assert isinstance(app.next_action_callout, _FakeLabelFrame)
    assert app.next_action_callout.kwargs.get("text") == "Next action"
    pack_forget_calls = [call for call in app.next_action_callout.calls if call[0] == "pack_forget"]
    assert pack_forget_calls, "the base next-action callout must be hidden by the guided shell"


def test_guided_shell_still_builds_a_populated_song_progress_panel(monkeypatch) -> None:
    """Hiding the redundant callout must not remove the guided shell's own
    primary panel -- it remains the single visible next-step surface."""

    _patch_widgets(monkeypatch)
    app = _FakeGuidedApp()

    song_progress = next(
        child
        for child in app.children
        if isinstance(child, _FakeLabelFrame) and child.kwargs.get("text") == "Song progress"
    )
    assert app.next_action_button.master.master is song_progress
    assert app.readiness_headline_var.get() == "Open or create a song project to begin"


def test_base_desktop_app_still_shows_its_own_next_action_callout(monkeypatch) -> None:
    """The non-guided `DesktopApp`/`ProductDesktopApp` layout is unaffected:
    only the guided shell hides the callout."""

    monkeypatch.setattr(desktop_shell.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(desktop_shell.ttk, "Label", _FakeLabel)
    monkeypatch.setattr(desktop_shell.ttk, "Button", _FakeButton)
    _patch_widgets(monkeypatch)

    app = object.__new__(desktop_shell.ProductDesktopApp)
    app.children = []
    app.winfo_children = lambda: list(app.children)
    app.song_var = _FakeVar()
    app.project_var = _FakeVar()
    app.next_action_var = _FakeVar()
    app.status_var = _FakeVar()
    app.score_var = _FakeVar()
    app.rights_note_var = _FakeVar()
    app.rights_source_var = _FakeVar()
    app.rights_class_var = _FakeVar()
    app.mapping_vars = {role: _FakeVar() for role in ArrangementRole}
    app.mapping_status_vars = {role: _FakeVar() for role in ArrangementRole}
    app.new_project_dialog = lambda: None
    app.open_project_dialog = lambda: None
    app.run_automatic_steps = lambda: None
    app.refresh_project = lambda: None
    app.register_score_dialog = lambda: None
    app.record_rights_review = lambda: None
    app.open_song_workspace = lambda: None

    desktop_shell.ProductDesktopApp._build_layout(app)

    assert isinstance(app.next_action_callout, _FakeLabelFrame)
    pack_forget_calls = [call for call in app.next_action_callout.calls if call[0] == "pack_forget"]
    assert not pack_forget_calls, "the non-guided shell must keep showing its own next-action callout"
