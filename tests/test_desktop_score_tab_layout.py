"""Regression coverage for Product Reality issue #304.

On a constrained packaged-window height, the Score & Mappings tab's actual
human-confirmation gate controls (the Bass/Lead/Rhythm mapping comboboxes and
Confirm buttons) were laid out *below* a tall fixed-height track-inventory
table. The notebook area can be squeezed short by the shell chrome stacked
above it (readiness banner, next-action callout, live diagnostics panel), and
the tab had no scroll path, so the required controls were unreachable on a
real 1600x960 Windows laptop and the project could not advance.

These tests exercise the real ``DesktopApp._build_layout`` source directly
against lightweight recording stand-ins for the ``tkinter``/``ttk`` widget
classes it constructs, so the fix is regression-tested without requiring a
real display server (this repository's GUI modules are never exercised
against a live Tk root in tests; see ``tests/test_desktop_theme.py`` for the
same no-display convention applied to styling instead of layout).
"""

from __future__ import annotations

from rocksmith_cdlc_generator import desktop_app
from rocksmith_cdlc_generator.score_source import ArrangementRole


class _FakeVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
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

    def __getattr__(self, name: str):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def _record(*args: object, **kwargs: object):
            self.calls.append((name, args, kwargs))
            return None

        # Cache so repeated lookups (e.g. passing `.yview` as a callback and
        # later asserting on it) return the identical callable.
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


class _FakeApp:
    """Stand-in `self` carrying only what `_build_layout` reads before assigning it."""

    def __init__(self) -> None:
        self.song_var = _FakeVar()
        self.project_var = _FakeVar()
        self.next_action_var = _FakeVar()
        self.status_var = _FakeVar()
        self.score_var = _FakeVar()
        self.rights_note_var = _FakeVar()
        self.rights_source_var = _FakeVar()
        self.rights_class_var = _FakeVar()
        self.mapping_vars = {role: _FakeVar() for role in ArrangementRole}
        self.new_project_dialog = lambda: None
        self.open_project_dialog = lambda: None
        self.run_automatic_steps = lambda: None
        self.refresh_project = lambda: None
        self.register_score_dialog = lambda: None
        self.record_rights_review = lambda: None


def _build_fake_layout(monkeypatch) -> _FakeApp:
    monkeypatch.setattr(desktop_app.ttk, "Frame", _FakeFrame)
    monkeypatch.setattr(desktop_app.ttk, "LabelFrame", _FakeLabelFrame)
    monkeypatch.setattr(desktop_app.ttk, "Label", _FakeLabel)
    monkeypatch.setattr(desktop_app.ttk, "Button", _FakeButton)
    monkeypatch.setattr(desktop_app.ttk, "Entry", _FakeEntry)
    monkeypatch.setattr(desktop_app.ttk, "Combobox", _FakeCombobox)
    monkeypatch.setattr(desktop_app.ttk, "Treeview", _FakeTreeview)
    monkeypatch.setattr(desktop_app.ttk, "Notebook", _FakeNotebook)
    monkeypatch.setattr(desktop_app.ttk, "Scrollbar", _FakeScrollbar)
    monkeypatch.setattr(desktop_app.tk, "Text", _FakeText)

    app = _FakeApp()
    desktop_app.DesktopApp._build_layout(app)
    return app


def test_mapping_confirmation_controls_are_built_before_track_inventory(monkeypatch) -> None:
    """The human-confirmation gate must not be laid out after the track table.

    A control built after a tall fixed-height sibling in the same
    top-to-bottom `pack()` tab can be clipped off-screen with no way to reach
    it when the notebook area is short (issue #304). Building the mapping box
    first guarantees it renders directly under the tab header.
    """

    app = _build_fake_layout(monkeypatch)

    score_tab_children = app.score_tab.children
    mapping_box = next(child for child in score_tab_children if isinstance(child, _FakeLabelFrame))
    track_frame = app.track_tree.master

    assert track_frame in score_tab_children
    assert score_tab_children.index(mapping_box) < score_tab_children.index(track_frame)

    assert mapping_box.kwargs.get("text") == "Human-confirmed Rocksmith arrangement mappings"
    assert len(app.mapping_combos) == 3
    assert set(app.mapping_combos) == {ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm}


def test_track_inventory_has_its_own_vertical_scrollbar(monkeypatch) -> None:
    """The (informational, non-blocking) track table must remain fully reachable
    even when the tab has little vertical room left, via its own scrollbar."""

    app = _build_fake_layout(monkeypatch)

    track_frame = app.track_tree.master
    scrollbar = next(child for child in track_frame.children if isinstance(child, _FakeScrollbar))

    assert scrollbar.kwargs.get("orient") == "vertical"
    assert scrollbar.kwargs.get("command") is app.track_tree.yview
    configure_calls = [call for call in app.track_tree.calls if call[0] == "configure"]
    assert any(call[2].get("yscrollcommand") is scrollbar.set for call in configure_calls)
