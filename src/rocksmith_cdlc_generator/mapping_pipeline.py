from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from .fret_mapping import map_bass_transcription, map_reconciled_bass_chart, write_bass_mapping
from .fretboard import resolve_bass_tuning
from .mapping_quality import review_bass_mapping
from .reconciliation import ReconciledBassChart
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

    # A staged multi-arrangement package may reference the Bass XML being invalidated.
    # Match the Lead/Rhythm rebuild boundary: remove both DLC Builder preparation and
    # returned/staged PSARC state before publishing the replacement Bass mapping.
    for stale_dir in (project_dir / "build" / "dlcbuilder", project_dir / "build" / "staging"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
        if stale_dir.exists():
            raise OSError(f"Failed to invalidate stale package staging: {stale_dir}")


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
    tuning = resolve_bass_tuning(tuning_name)

    if source == "auto":
        selected = "reconciled" if reconciled_path.is_file() else "raw"
    else:
        selected = source

    if selected == "reconciled":
        if not reconciled_path.is_file():
            raise FileNotFoundError(
                f"Reconciled Bass chart not found: {reconciled_path}. Run cdlc reconcile-bass first or use --source raw."
            )
        chart = ReconciledBassChart.model_validate_json(reconciled_path.read_text(encoding="utf-8"))
        mapping = map_reconciled_bass_chart(chart, tuning, max_fret=max_fret)
    else:
        if not raw_path.is_file():
            raise FileNotFoundError(
                f"Bass transcription not found: {raw_path}. Run cdlc transcribe-bass first."
            )
        mapping = map_bass_transcription(read_transcription(raw_path), tuning, max_fret=max_fret)

    review = review_bass_mapping(mapping)
    mapping_path = project_dir / "charts" / "bass_mapped.json"
    review_path = project_dir / "review" / "bass_mapping_review.json"

    # Validation, XML and package staging describe the previous Bass mapping. Remove
    # them before replacing mapping authority so a cleanup failure cannot leave a newly
    # mapped chart beside stale output that still appears installable/current.
    _invalidate_bass_mapping_derivatives(project_dir)
    write_bass_mapping(mapping, mapping_path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    return {"mapping": mapping_path, "review": review_path}
