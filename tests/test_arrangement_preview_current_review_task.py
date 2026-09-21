from __future__ import annotations

from rocksmith_cdlc_generator.arrangement_preview_ui import format_current_review_task
from rocksmith_cdlc_generator.song_preview import PreviewReviewItem
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _item(*, string_index: int | None = 1, fret: int | None = 8) -> PreviewReviewItem:
    return PreviewReviewItem(
        review_id="lead:0:4",
        instrument="lead",
        part_name="Lead Guitar",
        event_index=4,
        start_seconds=77.756,
        duration_seconds=0.5,
        midi=68,
        note_name="G#4",
        string_index=string_index,
        fret=fret,
        import_confidence=0.8,
        trust_class=SourceTrustClass.symbolic_unverified,
    )


def test_current_review_task_is_compact_and_actionable() -> None:
    text = format_current_review_task(_item(), index=2, total=12)

    assert text == (
        "Current review task 3/12: Lead at 77.756s · G#4 · string 2, fret 8"
    )


def test_current_review_task_reports_unresolved_position() -> None:
    text = format_current_review_task(
        _item(string_index=None, fret=None), index=0, total=1
    )

    assert "physical position unresolved" in text


def test_current_review_task_prompts_navigation_before_selection() -> None:
    assert format_current_review_task(None, index=None, total=4) == (
        "Current review task: 4 event(s) waiting — use Next review to begin."
    )


def test_current_review_task_handles_empty_queue() -> None:
    assert format_current_review_task(None, index=None, total=0) == (
        "Current review task: none — no arrangement events currently require review."
    )
