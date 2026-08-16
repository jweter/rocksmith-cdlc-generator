from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .librosa_transcription import LibrosaPyinBassTranscriber
from .midi_export import write_bass_midi
from .transcription import write_notes_csv, write_transcription
from .transcription_quality import review_bass_transcription


ProgressCallback = Callable[[float, str], None]


def _select_bass_input(project_dir: Path, input_path: Path | None) -> Path:
    if input_path is not None:
        return input_path.resolve()

    bass_stem = project_dir / "stems" / "bass.wav"
    if bass_stem.is_file():
        return bass_stem

    return project_dir / "audio" / "normalized.wav"


def analyze_project_bass(
    project_dir: Path,
    *,
    engine: str = "librosa-pyin",
    input_path: Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    audio_path = _select_bass_input(project_dir, input_path)
    if not audio_path.is_file():
        raise FileNotFoundError(
            f"Bass transcription input not found: {audio_path}. Normalize the project first, generate a bass stem, or pass --input."
        )

    if engine == "librosa-pyin":
        transcriber = LibrosaPyinBassTranscriber()
    else:
        raise ValueError(f"Unsupported bass transcription engine: {engine}")

    def analysis_progress(percent: float, message: str) -> None:
        if progress_callback is not None:
            progress_callback(percent * 0.95, message)

    transcription = transcriber.transcribe(
        audio_path,
        progress_callback=analysis_progress if progress_callback is not None else None,
    )
    if progress_callback is not None:
        progress_callback(96.0, "Reviewing transcription confidence")
    review = review_bass_transcription(transcription)

    raw_path = project_dir / "analysis" / "bass_raw.json"
    csv_path = project_dir / "analysis" / "bass_notes.csv"
    midi_path = project_dir / "charts" / "bass.mid"
    review_path = project_dir / "review" / "bass_transcription_review.json"

    if progress_callback is not None:
        progress_callback(98.0, "Writing Bass draft artifacts")
    write_transcription(transcription, raw_path)
    write_notes_csv(transcription, csv_path)
    write_bass_midi(transcription, midi_path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    if progress_callback is not None:
        progress_callback(100.0, "Bass draft artifacts written")

    return {
        "input": audio_path,
        "transcription": raw_path,
        "notes_csv": csv_path,
        "midi": midi_path,
        "review": review_path,
    }
