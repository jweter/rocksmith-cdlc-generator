from __future__ import annotations

from pathlib import Path

from .beat_quality import review_tempo_map
from .beat_trackers import create_beat_tracker
from .beats import write_beats_csv, write_tempo_map


def analyze_project_tempo(project_dir: Path, *, engine: str = "librosa") -> dict[str, Path]:
    project_dir = project_dir.resolve()
    audio = project_dir / "audio" / "normalized.wav"
    if not audio.is_file():
        raise FileNotFoundError(
            f"Canonical audio not found: {audio}. Run 'cdlc normalize' first."
        )

    tracker = create_beat_tracker(engine)
    tempo_map = tracker.analyze(audio)
    analysis_dir = project_dir / "analysis"
    tempo_path = analysis_dir / "tempo_map.json"
    beats_path = analysis_dir / "beats.csv"
    review_path = project_dir / "review" / "beat_grid_review.json"

    write_tempo_map(tempo_map, tempo_path)
    write_beats_csv(tempo_map, beats_path)
    review = review_tempo_map(tempo_map)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    return {
        "tempo_map": tempo_path,
        "beats_csv": beats_path,
        "review": review_path,
    }
