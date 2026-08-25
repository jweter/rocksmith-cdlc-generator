from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import ProjectManifest
from .score_preview import load_score_fanout_preview_snapshot

ScoreCoverageState = Literal["UNAVAILABLE", "COMPLETE", "PARTIAL"]
ScoreCoverageBasis = Literal["none", "mapped_score_timebase", "mapped_note_events"]


class ScoreCoverageAssessment(BaseModel):
    """Read-only comparison between structured-score extent and recording extent.

    Coverage is intentionally evidence, not musical authority. A PARTIAL result never
    invents notes and does not assert what the missing passage should contain.
    """

    model_config = ConfigDict(frozen=True)

    state: ScoreCoverageState
    basis: ScoreCoverageBasis
    recording_duration_seconds: float = Field(ge=0.0)
    score_end_seconds: float | None = Field(default=None, ge=0.0)
    covered_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    uncovered_tail_seconds: float | None = Field(default=None, ge=0.0)
    partial_threshold_seconds: float = Field(ge=0.0)


def assess_mapped_score_coverage(
    recording_duration_seconds: float,
    *,
    mapped_score_beats: Iterable[float] = (),
    mapped_note_end_times: Iterable[float] = (),
    minimum_material_tail_seconds: float = 5.0,
    minimum_material_tail_fraction: float = 0.05,
) -> ScoreCoverageAssessment:
    """Classify whether a mapped structured score materially undershoots a recording.

    Prefer the mapped score beat/timebase extent because it preserves explicit trailing
    rests and empty measures. Falling back to last mapped note time is intentionally less
    authoritative and is used only when no score beats are available.

    A small tail is tolerated because recordings commonly contain ring-out/fade/silence.
    The default materiality threshold is the larger of five seconds or five percent of
    the recording. This diagnostic never extrapolates the score beyond observed evidence.
    """

    duration = max(0.0, float(recording_duration_seconds))
    minimum_tail = max(0.0, float(minimum_material_tail_seconds))
    minimum_fraction = max(0.0, float(minimum_material_tail_fraction))
    threshold = max(minimum_tail, duration * minimum_fraction)

    beats = [max(0.0, float(value)) for value in mapped_score_beats]
    note_ends = [max(0.0, float(value)) for value in mapped_note_end_times]

    if beats:
        score_end = max(beats)
        basis: ScoreCoverageBasis = "mapped_score_timebase"
    elif note_ends:
        score_end = max(note_ends)
        basis = "mapped_note_events"
    else:
        return ScoreCoverageAssessment(
            state="UNAVAILABLE",
            basis="none",
            recording_duration_seconds=duration,
            partial_threshold_seconds=threshold,
        )

    uncovered = max(0.0, duration - score_end)
    if duration <= 0.0:
        covered_percent = 100.0
    else:
        covered_percent = min(100.0, max(0.0, (score_end / duration) * 100.0))
    state: ScoreCoverageState = "PARTIAL" if uncovered > threshold else "COMPLETE"

    return ScoreCoverageAssessment(
        state=state,
        basis=basis,
        recording_duration_seconds=duration,
        score_end_seconds=score_end,
        covered_percent=covered_percent,
        uncovered_tail_seconds=uncovered,
        partial_threshold_seconds=threshold,
    )


def assess_project_score_coverage(project_dir: Path) -> ScoreCoverageAssessment:
    """Assess the current human-confirmed score fan-out on the recording clock."""

    project = project_dir.expanduser().resolve()
    manifest = ProjectManifest.load(project)
    preview = load_score_fanout_preview_snapshot(project)
    note_ends = [
        note.start_seconds + note.duration_seconds
        for arrangement in preview.arrangements
        for note in arrangement.notes
    ]
    return assess_mapped_score_coverage(
        manifest.source_metadata.duration_seconds,
        mapped_score_beats=preview.beat_times_seconds,
        mapped_note_end_times=note_ends,
    )


def partial_score_warning_message(assessment: ScoreCoverageAssessment) -> str:
    """Human-facing explanation for a material structured-score shortfall."""

    if assessment.state != "PARTIAL":
        raise ValueError("partial_score_warning_message requires a PARTIAL assessment")
    assert assessment.score_end_seconds is not None
    assert assessment.covered_percent is not None
    assert assessment.uncovered_tail_seconds is not None
    return (
        "Structured score coverage ends at approximately "
        f"{assessment.score_end_seconds:.2f}s of a {assessment.recording_duration_seconds:.2f}s recording "
        f"({assessment.covered_percent:.1f}% coverage; {assessment.uncovered_tail_seconds:.2f}s uncovered). "
        "The uncovered tail has no symbolic score authority. No missing notes were extrapolated or invented; "
        "use another score source, audio-derived transcription, or explicit manual authoring for that region."
    )
