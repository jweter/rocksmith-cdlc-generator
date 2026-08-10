from __future__ import annotations

from pathlib import Path

from .librosa_transcription import LibrosaPyinBassTranscriber
from .transcription import write_notes_csv, write_transcription
from .transcription_quality import review_bass_transcription


def analyze_project_bass(
    project_dir: Path,
    *,
    engine: str = "librosa-pyin",
    input_path: Path | None = None,
) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    audio_path = input_path.resolve() if input_path else project_dir / "audio" / "normalized.wav"
    if not audio_path.is_file():
        raise FileNotFoundError(
            f"Bass transcription input not found: {audio_path}. Normalize the project first or pass --input."
        )

    if engine == "librosa-pyin":
        transcriber = LibrosaPyinBassTranscriber()
    else:
        raise ValueError(f"Unsupported bass transcription engine: {engine}")

    transcription = transcriber.transcribe(audio_path)
    review = review_bass_transcription(transcription)

    json_path = project_dir / "analysis" / "bass_notes.json"
    csv_path = project_dir / "analysis" / "bass_notes.csv"
    review_path = project_dir / "review" / "bass_transcription_review.json"

    write_transcription(transcription, json_path)
    write_notes_csv(transcription, csv_path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    return {
        "transcription": json_path,
        "notes_csv": csv_path,
        "review": review_path,
    }
