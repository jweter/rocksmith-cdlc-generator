from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator.song_workspace_ui import SongWorkspaceWindow
from rocksmith_cdlc_generator.song_workspace import WorkspaceReviewItem


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value


class _Tree:
    """Minimal stand-in for ttk.Treeview covering only what refresh touches."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, tuple, tuple]] = []

    def delete(self, *iids: str) -> None:
        remaining = [(iid, values, tags) for iid, values, tags in self.rows if iid not in iids]
        self.rows = remaining

    def get_children(self) -> tuple[str, ...]:
        return tuple(iid for iid, _values, _tags in self.rows)

    def insert(self, _parent: str, _index: str, iid: str, values: tuple, tags: tuple = ()) -> None:
        self.rows.append((iid, values, tags))


def _fail(message: str) -> WorkspaceReviewItem:
    return WorkspaceReviewItem(
        arrangement="bass",
        code="unmapped_bass_note",
        severity="FAIL",
        stage="mapping",
        message=message,
        time_seconds=8.748,
        priority=90,
    )


def test_review_detail_reflects_populated_queue_not_a_stale_empty_message() -> None:
    """Reproduces the #304 Product Reality report: the Review Queue tab showed
    visible FAIL rows while the detail panel still said "No persisted
    validation findings are currently queued." because that text was only ever
    set on an empty-queue refresh and never cleared on a later refresh that
    populated the tree.
    """
    window = SimpleNamespace(review_tree=_Tree(), review_detail_var=_Var())

    # First refresh: empty queue, matching app startup / not-yet-validated state.
    SongWorkspaceWindow._refresh_review_queue(window, SimpleNamespace(review_queue=[]))
    assert window.review_detail_var.value == "No persisted validation findings are currently queued."

    # Second refresh: automation ran and produced FAIL rows, but the user has
    # not clicked a row yet (no <<TreeviewSelect>> event fired).
    queue = [_fail("Bass note 12 has no playable string/fret position.")]
    SongWorkspaceWindow._refresh_review_queue(window, SimpleNamespace(review_queue=queue))

    assert len(window.review_tree.rows) == 1
    assert "No persisted validation findings are currently queued" not in window.review_detail_var.value
    assert "1 items queued" in window.review_detail_var.value
    assert "1 failures" in window.review_detail_var.value
    assert "Select a row to see details" in window.review_detail_var.value


def test_review_detail_still_reports_empty_queue_when_queue_stays_empty() -> None:
    window = SimpleNamespace(review_tree=_Tree(), review_detail_var=_Var())

    SongWorkspaceWindow._refresh_review_queue(window, SimpleNamespace(review_queue=[]))
    SongWorkspaceWindow._refresh_review_queue(window, SimpleNamespace(review_queue=[]))

    assert window.review_tree.rows == []
    assert window.review_detail_var.value == "No persisted validation findings are currently queued."


def test_review_detail_counts_warnings_and_failures_separately() -> None:
    window = SimpleNamespace(review_tree=_Tree(), review_detail_var=_Var())

    queue = [
        _fail("Bass note 12 has no playable string/fret position."),
        WorkspaceReviewItem(
            arrangement="lead",
            code="low_confidence_position",
            severity="WARNING",
            stage="review",
            message="Confidence below threshold.",
            priority=40,
        ),
    ]
    SongWorkspaceWindow._refresh_review_queue(window, SimpleNamespace(review_queue=queue))

    assert "2 items queued" in window.review_detail_var.value
    assert "1 failures" in window.review_detail_var.value
    assert "1 warnings" in window.review_detail_var.value


def test_review_queue_rows_render_non_color_alone_severity_status_with_tags() -> None:
    """#305: the Review Queue tab's Severity column previously rendered the raw
    ``WorkspaceReviewItem.severity`` string ("FAIL"/"WARNING"/"INFO") with no color,
    symbol, or weight differentiation (desktop-ui-audit.md finding #2). Each row
    should now carry the shared symbol+label semantic-status text plus a Treeview
    tag naming its ``StatusState`` so ``_build_review_queue``'s
    ``tag_configure(state, foreground=...)`` calls can color it.
    """
    window = SimpleNamespace(review_tree=_Tree(), review_detail_var=_Var())

    queue = [
        _fail("Bass note 12 has no playable string/fret position."),
        WorkspaceReviewItem(
            arrangement="lead",
            code="low_confidence_position",
            severity="WARNING",
            stage="review",
            message="Confidence below threshold.",
            priority=40,
        ),
        WorkspaceReviewItem(
            arrangement="rhythm",
            code="tie_continuation",
            severity="INFO",
            stage="review",
            message="Tie continues from prior event.",
            priority=10,
        ),
    ]
    SongWorkspaceWindow._refresh_review_queue(window, SimpleNamespace(review_queue=queue))

    severities = {values[0]: tags for _iid, values, tags in window.review_tree.rows}
    # Each severity text pairs a distinct symbol with the label (never color alone),
    # and its Treeview tag names the matching StatusState for tag_configure coloring.
    assert severities["✗ FAIL"] == ("fail",)
    assert severities["⚠ WARNING"] == ("warning",)
    assert severities["ℹ INFO"] == ("info",)
