from __future__ import annotations

from pathlib import Path
from typing import Literal

from .alignment import AlignmentReport
from .fret_mapping import map_bass_transcription, map_reconciled_bass_chart, write_bass_mapping
from .fretboard import BassTuning, resolve_bass_tuning
from .mapping_quality import review_bass_mapping
from .package_generation import invalidate_package_state
from .reconciliation import (
    ReconciledBassChart,
    reconcile_project_bass,
    reconciled_bass_chart_is_current,
)
from .transcription import read_transcription


def _invalidate_bass_mapping_derivatives(project_dir: Path) -> None:
    """Remove downstream artifacts that cannot survive a new Bass mapping authority."""

    for relative in (
        "review/validation_report.json",
        "review/flags.json",
        "review/summary.md",
        "eof/arr_bass_RS2.xml",
        "eof/export_manifest.json",
        "eof/README.md",
    ):
        (project_dir / relative).unlink(missing_ok=True)

    invalidate_package_state(project_dir)


def _infer_reconciled_bass_tuning(
    chart: ReconciledBassChart,
    fallback_tuning: BassTuning | None = None,
) -> BassTuning | None:
    """Recover reviewed symbolic Bass tuning from string/fret/pitch evidence.

    Reconciliation preserves Guitar Pro symbolic string/fret coordinates. For any
    symbolic note, open-string pitch is therefore ``midi - fret``.

    Prefer complete four-string evidence. If the score only uses a subset of strings,
    partial evidence may still establish a uniformly transposed version of the configured
    fallback tuning (for example E Standard -> Eb Standard). Require at least two observed
    strings and the same semitone offset on every observed string before extrapolating.
    This deliberately does not guess drop/alternate tunings from incomplete evidence.
    """

    open_by_string: dict[int, int] = {}
    for note in chart.notes:
        if note.status == "audio_only" or note.string_index is None or note.fret is None:
            continue
        if not 0 <= note.string_index <= 3:
            continue
        open_pitch = note.midi - note.fret
        if not 0 <= open_pitch <= 127:
            return None
        previous = open_by_string.get(note.string_index)
        if previous is not None and previous != open_pitch:
            return None
        open_by_string[note.string_index] = open_pitch

    if set(open_by_string) == {0, 1, 2, 3}:
        pitches = tuple(open_by_string[index] for index in range(4))
        try:
            return BassTuning(name="Reviewed symbolic source", open_midi=pitches)
        except ValueError:
            return None

    if fallback_tuning is None or len(open_by_string) < 2:
        return None

    offsets = {
        open_pitch - fallback_tuning.open_midi[string_index]
        for string_index, open_pitch in open_by_string.items()
    }
    if len(offsets) != 1:
        return None

    offset = next(iter(offsets))
    pitches = tuple(open_pitch + offset for open_pitch in fallback_tuning.open_midi)
    if any(not 0 <= pitch <= 127 for pitch in pitches):
        return None
    if any(pitches[index] != pitch for index, pitch in open_by_string.items()):
        return None

    try:
        return BassTuning(
            name=f"Reviewed symbolic source ({offset:+d} semitone offset)",
            open_midi=pitches,
        )
    except ValueError:
        return None


def _refresh_stale_reconciliation(project_dir: Path, reconciled_path: Path) -> None:
    """Rebuild stale reconciliation from the already reviewed alignment/source authority.

    This is intentionally deterministic and does not make a new musical/source decision.
    It only re-materializes derived state using the current reconciliation algorithm. If
    the alignment/source authority is missing or invalid, fail closed rather than falling
    back to raw audio and silently changing the arrangement source.
    """

    if not reconciled_path.is_file() or reconciled_bass_chart_is_current(reconciled_path):
        return

    alignment_path = project_dir / "analysis" / "alignment.json"
    if not alignment_path.is_file():
        raise FileNotFoundError(
            "Stale reconciled Bass chart cannot be refreshed because analysis/alignment.json is missing."
        )
    alignment = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    source_path = Path(alignment.source_path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(
            f"Stale reconciled Bass chart cannot be refreshed because its aligned source is missing: {source_path}"
        )
    reconcile_project_bass(
        project_dir,
        source_path,
        alignment_path=alignment_path,
    )


def map_project_bass(
    project_dir: Path,
    *,
    tuning_name: str = "E Standard",
    max_fret: int = 24,
    source: Literal["auto", "raw", "reconciled"] = "auto",
) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    raw_path = project_dir / "analysis" / "bass_raw.json"
    reconciled_path = project_dir / "charts" / "bass_reconciled.json"
    fallback_tuning = resolve_bass_tuning(tuning_name)

    if source in {"auto", "reconciled"} and reconciled_path.is_file():
        _refresh_stale_reconciliation(project_dir, reconciled_path)

    if source == "auto":
        selected = "reconciled" if reconciled_path.is_file() else "raw"
    else:
        selected = source

    if selected == "reconciled":
        if not reconciled_path.is_file():
            raise FileNotFoundError(
                f"Reconciled Bass chart not found: {reconciled_path}. Run cdlc reconcile-bass first or use --source raw."
            )
        if not reconciled_bass_chart_is_current(reconciled_path):
            raise ValueError(
                "Reconciled Bass chart is stale and could not be refreshed safely; rerun cdlc reconcile-bass before mapping."
            )
        chart = ReconciledBassChart.model_validate_json(reconciled_path.read_text(encoding="utf-8"))
        tuning = _infer_reconciled_bass_tuning(chart, fallback_tuning) or fallback_tuning
        mapping = map_reconciled_bass_chart(chart, tuning, max_fret=max_fret)
    else:
        if not raw_path.is_file():
            raise FileNotFoundError(
                f"Bass transcription not found: {raw_path}. Run cdlc transcribe-bass first."
            )
        mapping = map_bass_transcription(read_transcription(raw_path), fallback_tuning, max_fret=max_fret)

    review = review_bass_mapping(mapping)
    mapping_path = project_dir / "charts" / "bass_mapped.json"
    review_path = project_dir / "review" / "bass_mapping_review.json"

    _invalidate_bass_mapping_derivatives(project_dir)
    write_bass_mapping(mapping, mapping_path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    return {"mapping": mapping_path, "review": review_path}
