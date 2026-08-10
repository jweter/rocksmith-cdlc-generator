from __future__ import annotations

from pathlib import Path
from statistics import median

from .transcription import BassTranscription, NoteEvent


class LibrosaPyinBassTranscriber:
    name = "librosa-pyin"

    def __init__(
        self,
        *,
        fmin_hz: float = 41.0,
        fmax_hz: float = 523.3,
        hop_length: int = 256,
        minimum_note_seconds: float = 0.08,
        review_threshold: float = 0.55,
    ) -> None:
        self.fmin_hz = fmin_hz
        self.fmax_hz = fmax_hz
        self.hop_length = hop_length
        self.minimum_note_seconds = minimum_note_seconds
        self.review_threshold = review_threshold

    @property
    def version(self) -> str | None:
        try:
            import librosa

            return librosa.__version__
        except ImportError:
            return None

    def transcribe(self, audio_path: Path) -> BassTranscription:
        try:
            import librosa
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "librosa transcription dependencies are not installed. "
                "Install with: pip install -e '.[beat]'"
            ) from exc

        audio_path = audio_path.resolve()
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        if y.size == 0:
            raise ValueError(f"Audio file is empty: {audio_path}")

        onset_envelope = librosa.onset.onset_strength(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
        )
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_envelope,
            sr=sr,
            hop_length=self.hop_length,
            units="frames",
            backtrack=True,
            energy=onset_envelope,
        )
        onset_times = librosa.frames_to_time(
            onset_frames,
            sr=sr,
            hop_length=self.hop_length,
        )

        f0, voiced_flag, voiced_prob = librosa.pyin(
            y,
            fmin=self.fmin_hz,
            fmax=self.fmax_hz,
            sr=sr,
            hop_length=self.hop_length,
        )
        frame_times = librosa.times_like(f0, sr=sr, hop_length=self.hop_length)

        duration = len(y) / float(sr)
        boundaries = [0.0]
        boundaries.extend(float(value) for value in onset_times if value > 0.02)
        boundaries.append(duration)
        boundaries = sorted(set(boundaries))

        notes: list[NoteEvent] = []
        for start, end in zip(boundaries, boundaries[1:]):
            note_duration = end - start
            if note_duration < self.minimum_note_seconds:
                continue

            mask = (frame_times >= start) & (frame_times < end)
            if not np.any(mask):
                continue

            segment_f0 = f0[mask]
            segment_voiced = voiced_flag[mask]
            segment_prob = voiced_prob[mask]
            valid = segment_voiced & np.isfinite(segment_f0)
            if not np.any(valid):
                continue

            voiced_fraction = float(np.count_nonzero(valid) / np.count_nonzero(mask))
            pitch_hz = float(np.median(segment_f0[valid]))
            midi_float = float(librosa.hz_to_midi(pitch_hz))
            midi = int(round(midi_float))
            pitch_stability = max(0.0, 1.0 - min(abs(midi_float - midi) / 0.5, 1.0))
            voiced_confidence = float(np.median(segment_prob[valid]))
            pitch_confidence = max(0.0, min(1.0, voiced_confidence * pitch_stability))

            onset_index = int(np.argmin(np.abs(frame_times - start)))
            local_onset_strength = (
                float(onset_envelope[min(onset_index, len(onset_envelope) - 1)])
                if len(onset_envelope)
                else 0.0
            )
            envelope_peak = float(np.max(onset_envelope)) if len(onset_envelope) else 0.0
            timing_confidence = (
                max(0.0, min(1.0, local_onset_strength / envelope_peak))
                if envelope_peak > 0.0
                else 0.5
            )
            confidence = max(
                0.0,
                min(1.0, 0.55 * pitch_confidence + 0.25 * voiced_fraction + 0.20 * timing_confidence),
            )

            notes.append(
                NoteEvent(
                    start=float(start),
                    duration=float(note_duration),
                    midi=midi,
                    confidence=confidence,
                    pitch_confidence=pitch_confidence,
                    timing_confidence=timing_confidence,
                    review_required=confidence < self.review_threshold,
                )
            )

        return BassTranscription(
            engine=self.name,
            engine_version=librosa.__version__,
            source_path=str(audio_path),
            sample_rate_hz=int(sr),
            notes=notes,
        )
