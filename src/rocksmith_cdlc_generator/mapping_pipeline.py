from __future__ import annotations

from pathlib import Path

from .fret_mapping import map_bass_transcription, write_bass_mapping
from .fretboard import resolve_bass_tuning
from .mapping_quality import review_bass_mapping
from .transcription import read_transcription


def map_project_bass(
    project_dir: Path,
    *,
    tuning_name: str = "E Standard",
    max_fret: int = 24,
) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    transcription_path = project_dir / "analysis" / "bass_raw.json"
    if not transcription_path.is_file():
        raise FileNotFoundError(
            f"Bass transcription not found: {transcription_path}. Run cdlc transcribe-bass first."
        )

    transcription = read_transcription(transcription_path)
    tuning = resolve_bass_tuning(tuning_name)
    mapping = map_bass_transcription(
        transcription,
        tuning,
        max_fret=max_fret,
    )
    review = review_bass_mapping(mapping)

    mapping_path = project_dir / "charts" / "bass_mapped.json"
    review_path = project_dir / "review" / "bass_mapping_review.json"
    write_bass_mapping(mapping, mapping_path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    return {
        "mapping": mapping_path,
        "review": review_path,
    }
