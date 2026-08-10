from __future__ import annotations

from pathlib import Path

from .beats import BeatEvent, TempoMap


def _librosa_version() -> str | None:
    try:
        import librosa
    except ImportError:
        return None
    return getattr(librosa, "__version__", None)


def _require_librosa():
    try:
        import librosa
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            'Beat analysis requires the optional beat dependencies. '
            'Install with: pip install -e ".[beat]"'
        ) from exc
    return librosa, np


def _scalar_tempo(value) -> float:
    try:
        return float(value.item())
    except (AttributeError, ValueError):
        return float(value)


def _events_from_times(
    *,
    times,
    bpm: float,
    salience,
    frames,
    engine: str,
) -> TempoMap:
    beat_events: list[BeatEvent] = []
    maximum = float(max(salience)) if len(salience) else 0.0
    for index, (time_value, frame) in enumerate(zip(times, frames)):
        beat_number = (index % 4) + 1
        measure = (index // 4) + 1
        confidence = 0.0
        frame_index = int(frame)
        if maximum > 0.0 and 0 <= frame_index < len(salience):
            confidence = min(1.0, max(0.0, float(salience[frame_index]) / maximum))
        beat_events.append(
            BeatEvent(
                time=float(time_value),
                beat=beat_number,
                measure=measure,
                bpm=bpm,
                confidence=confidence,
                is_downbeat=beat_number == 1,
            )
        )
    return TempoMap(
        engine=engine,
        engine_version=_librosa_version(),
        sample_rate_hz=44100,
        beats=beat_events,
    )


class LibrosaBeatTracker:
    """Dynamic-programming beat tracker using librosa.beat.beat_track."""

    name = "librosa-beat-track"
    version = None

    def analyze(self, audio_path: Path) -> TempoMap:
        librosa, _ = _require_librosa()
        y, sr = librosa.load(audio_path, sr=44100, mono=True)
        onset = librosa.onset.onset_strength(y=y, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset,
            sr=sr,
            units="frames",
        )
        bpm = _scalar_tempo(tempo)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        return _events_from_times(
            times=beat_times,
            bpm=bpm,
            salience=onset,
            frames=beat_frames,
            engine=self.name,
        )


class LibrosaPLPTracker:
    """Predominant-local-pulse tracker used as an independent rhythm baseline."""

    name = "librosa-plp"
    version = None

    def analyze(self, audio_path: Path) -> TempoMap:
        librosa, np = _require_librosa()
        y, sr = librosa.load(audio_path, sr=44100, mono=True)
        onset = librosa.onset.onset_strength(y=y, sr=sr)
        pulse = librosa.beat.plp(onset_envelope=onset, sr=sr)
        local_max = librosa.util.localmax(pulse)
        beat_frames = np.flatnonzero(local_max & (pulse > 0.25 * np.max(pulse)))
        if len(beat_frames) < 2:
            raise RuntimeError("PLP tracker did not detect enough beats")
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        intervals = np.diff(beat_times)
        bpm = float(60.0 / np.median(intervals))
        return _events_from_times(
            times=beat_times,
            bpm=bpm,
            salience=pulse,
            frames=beat_frames,
            engine=self.name,
        )


def create_beat_tracker(name: str):
    trackers = {
        "librosa": LibrosaBeatTracker,
        "librosa-plp": LibrosaPLPTracker,
    }
    try:
        return trackers[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown beat tracker: {name}") from exc
