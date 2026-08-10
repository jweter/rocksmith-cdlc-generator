from __future__ import annotations

from pathlib import Path
from typing import Literal

from .fret_mapping import map_bass_transcription, map_reconciled_bass_chart, write_bass_mapping
from .fretboard import resolve_bass_tuning
from .mapping_quality import review_bass_mapping
from .reconciliation import ReconciledBassChart
from .transcription import read_transcription


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
    write_bass_mapping(mapping, mapping_path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    return {"mapping": mapping_path, "review": review_path}
