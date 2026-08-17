from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from rocksmith_cdlc_generator import timing_review_ui
from rocksmith_cdlc_generator.timing_review_ui import (
    TimingReviewSongWorkspaceWindow,
    _acceptance_matches_display,
    _refit_preview_summary,
    _unique_refit_points,
)


def _point(index: int, candidate: float, refit: float, *, human: bool = False):
    return SimpleNamespace(
        source_beat_index=index,
        candidate_time_seconds=candidate,
        refit_time_seconds=refit,
        human_anchor=human,
    )


def _preview():
    shared = _point(8, 5.0, 5.1, human=True)
    return SimpleNamespace(
        max_abs_adjustment_seconds=0.125,
        regions=[
            SimpleNamespace(points=[_point(0, 1.0, 1.0, human=True), _point(4, 3.0, 3.05), shared]),
            SimpleNamespace(points=[shared, _point(12, 7.0, 7.125), _point(16, 9.0, 9.0, human=True)]),
        ],
    )


def test_unique_refit_points_deduplicates_neighboring_region_endpoint() -> None:
    points = _unique_refit_points(_preview())

    assert [point.source_beat_index for point in points] == [0, 4, 8, 12, 16]


def test_refit_preview_summary_reports_regions_beats_and_max_adjustment() -> None:
    assert _refit_preview_summary(_preview()) == (
        "Bounded refit preview: 2 reviewed region(s), 5 score beats, maximum adjustment 125.0 ms."
    )


def test_nearest_refit_point_text_shows_refit_delta_from_candidate() -> None:
    window = SimpleNamespace(
        score_timing_refit_preview=_preview(),
        _cursor_time=lambda: 7.0,
    )

    text = TimingReviewSongWorkspaceWindow._nearest_refit_point_text(window)

    assert "score beat 13" in text
    assert "7.125s" in text
    assert "+125.0 ms vs candidate" in text


def test_accept_score_refit_passes_exact_displayed_candidate_and_preview(monkeypatch, tmp_path: Path) -> None:
    candidate = object()
    preview = _preview()
    captured = {}

    monkeypatch.setattr(timing_review_ui.messagebox, "askyesno", lambda *args, **kwargs: True)

    def accept(project, *, expected_candidate, expected_preview):
        captured["project"] = project
        captured["candidate"] = expected_candidate
        captured["preview"] = expected_preview

    monkeypatch.setattr(timing_review_ui, "accept_score_timing_refit", accept)

    window = SimpleNamespace(
        project=tmp_path,
        candidate_shared_timeline=candidate,
        score_timing_refit_preview=preview,
        _refresh_score_anchor_review=lambda: None,
        _refresh_selected_beat_text=lambda: None,
        _draw_timeline=lambda: None,
    )

    TimingReviewSongWorkspaceWindow._accept_score_refit(window)

    assert captured == {
        "project": tmp_path,
        "candidate": candidate,
        "preview": preview,
    }


def test_acceptance_matches_only_exact_displayed_candidate_and_preview() -> None:
    displayed_candidate = object()
    displayed_preview = _preview()
    exact = SimpleNamespace(candidate=displayed_candidate, preview=displayed_preview)
    newer = SimpleNamespace(candidate=object(), preview=_preview())

    assert _acceptance_matches_display(exact, displayed_candidate, displayed_preview)
    assert not _acceptance_matches_display(newer, displayed_candidate, displayed_preview)


def test_refresh_does_not_mark_stale_displayed_preview_as_reviewed(monkeypatch, tmp_path: Path) -> None:
    displayed_candidate = object()
    displayed_preview = _preview()
    newer_acceptance = SimpleNamespace(candidate=object(), preview=_preview())
    review = SimpleNamespace(
        anchors=[
            SimpleNamespace(origin="confirmed_candidate"),
            SimpleNamespace(origin="manual_cursor"),
        ]
    )

    class Button:
        def __init__(self):
            self.config = {}

        def configure(self, **kwargs):
            self.config.update(kwargs)

    class Var:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value

    monkeypatch.setattr(timing_review_ui, "load_score_timing_anchor_review", lambda project: review)
    monkeypatch.setattr(
        timing_review_ui,
        "build_score_timing_refit_preview",
        lambda project, *, expected_candidate: displayed_preview,
    )
    monkeypatch.setattr(
        timing_review_ui,
        "load_current_score_timing_refit_acceptance",
        lambda project: newer_acceptance,
    )

    window = SimpleNamespace(
        project=tmp_path,
        candidate_shared_timeline=displayed_candidate,
        score_timing_anchor_review=None,
        score_timing_refit_preview=None,
        confirm_score_anchor_button=Button(),
        mark_score_anchor_button=Button(),
        accept_score_refit_button=Button(),
        score_anchor_var=Var(),
    )

    TimingReviewSongWorkspaceWindow._refresh_score_anchor_review(window)

    assert window.accept_score_refit_button.config == {
        "text": "Accept bounded refit review",
        "state": "normal",
    }
    assert "different current preview" in window.score_anchor_var.value
    assert "This exact bounded refit is human-reviewed." not in window.score_anchor_var.value
