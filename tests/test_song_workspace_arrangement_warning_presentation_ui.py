from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator.song_workspace import ArrangementWorkspaceState
from rocksmith_cdlc_generator.song_workspace_ui import SongWorkspaceWindow


class _Tree:
    """Minimal stand-in for ttk.Treeview covering only what _refresh_arrangements touches."""

    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def delete(self, *_iids: str) -> None:
        self.rows = []

    def get_children(self) -> tuple:
        return tuple(range(len(self.rows)))

    def insert(self, _parent: str, _index: str, **kwargs: object) -> None:
        self.rows.append(kwargs.get("values", ()))


def _arrangement(**updates: object) -> ArrangementWorkspaceState:
    data = dict(
        role="bass",
        configured=True,
        validation_state="WARNING",
        fail_count=0,
        warning_count=0,
        actionable_warning_count=0,
        export_xml_ready=False,
    )
    data.update(updates)
    return ArrangementWorkspaceState(**data)


def _window() -> SimpleNamespace:
    return SimpleNamespace(overview_tree=_Tree(), arrangement_tree=_Tree())


def test_overview_tree_pairs_actionable_groups_with_raw_warning_total() -> None:
    """#375: the Overview tab's per-arrangement validation cell must show the
    actionable/raw warning pair, never the raw total alone, so a project with
    thousands of repeated warnings that group to a handful of root causes does
    not read as unfixed.
    """
    window = _window()
    snapshot = SimpleNamespace(
        arrangements=[
            _arrangement(role="bass", warning_count=2851, actionable_warning_count=1),
            _arrangement(role="lead", warning_count=2046, actionable_warning_count=3),
            _arrangement(role="rhythm", warning_count=2981, actionable_warning_count=2),
        ]
    )

    SongWorkspaceWindow._refresh_arrangements(window, snapshot)

    validation_cells = [values[3] for values in window.overview_tree.rows]
    assert validation_cells == [
        "WARNING (0F/1/2851W)",
        "WARNING (0F/3/2046W)",
        "WARNING (0F/2/2981W)",
    ]


def test_overview_tree_omits_warning_suffix_when_validation_not_run() -> None:
    window = _window()
    snapshot = SimpleNamespace(
        arrangements=[_arrangement(role="bass", validation_state="NOT_RUN", warning_count=0, actionable_warning_count=0)]
    )

    SongWorkspaceWindow._refresh_arrangements(window, snapshot)

    assert window.overview_tree.rows[0][3] == "NOT_RUN"


def test_arrangements_tree_flags_column_shows_fails_and_actionable_raw_warnings() -> None:
    window = _window()
    snapshot = SimpleNamespace(
        arrangements=[
            _arrangement(role="bass", fail_count=0, warning_count=2851, actionable_warning_count=1),
        ]
    )

    SongWorkspaceWindow._refresh_arrangements(window, snapshot)

    flags_cell = window.arrangement_tree.rows[0][5]
    assert flags_cell == "0F · 1/2851W"


def test_arrangements_tree_flags_column_keeps_fail_count_explicit_and_unmerged() -> None:
    """FAIL counts must never be folded into the actionable/raw warning pairing."""
    window = _window()
    snapshot = SimpleNamespace(
        arrangements=[
            _arrangement(
                role="bass",
                validation_state="FAIL",
                fail_count=2,
                warning_count=5,
                actionable_warning_count=1,
            ),
        ]
    )

    SongWorkspaceWindow._refresh_arrangements(window, snapshot)

    flags_cell = window.arrangement_tree.rows[0][5]
    assert flags_cell == "2F · 1/5W"
