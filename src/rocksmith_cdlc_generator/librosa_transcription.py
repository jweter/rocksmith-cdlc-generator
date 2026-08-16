from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .transcription import BassTranscription, NoteEvent


ProgressCallback = Callable[[float, str], None]


def _analysis_windows(
    total_samples: int,
    sample_rate_hz: int,
    *,
    chunk_seconds: float,
    overlap_seconds: float,
) -> list[tuple[int, int, int, int]]:
    """Return deterministic context/core windows for bounded long-song analysis.

    Each tuple is ``(context_start, core_start, core_end, context_end)`` in samples.
    Core windows partition the source exactly once. Context overlap exists only to give
    onset/pitch analysis stable evidence near a boundary; notes are accepted only when
    their onset falls inside that window's core interval.
    """

    if total_samples < 1:
        return []
    if sample_rate_hz < 1:
        raise ValueError("sample_rate_hz must be positive")
    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be positive")
    if overlap_seconds < 0:
        raise ValueError("overlap_seconds cannot be negative")

    chunk_samples = max(1, int(round(chunk_seconds * sample_rate_hz)))
    overlap_samples = max(0, int(round(overlap_seconds * sample_rate_hz)))
    windows: list[tuple[int, int, int, int]] = []
    core_start = 0
    while core_start < total_samples:
        core_end = min(total_samples, core_start + chunk_samples)
        context_start = max(0, core_start - overlap_samples)
        context_end = min(total_samples, core_end + overlap_samples)
        windows.append((context_start, core_start, core_end, context_end))
        core_start = core_end
    return windows


def _append_chunk_observations(
    notes: list[NoteEvent],
    segment_notes: list[NoteEvent],
    *,
    context_offset_seconds: float,
    core_start_seconds: float,
    core_end_seconds: float,
    is_last: bool,
) -> None:
    """Append core-owned notes and stitch matching continuations across chunk boundaries.

    A note whose observed onset is in the left context is not a new core-owned onset.
    When that observation crosses the current core boundary and matches the most recent
    overlapping note of the same pitch, it is continuation evidence for that prior note.
    Extend the prior duration to the observed end instead of discarding the continuation.
    This can repeat across several chunks, so sustained notes are not capped by overlap.
    """

    for note in segment_notes:
        global_start = context_offset_seconds + note.start
        global_end = global_start + note.duration

        if global_start < core_start_seconds and global_end > core_start_seconds:
            candidates = [
                (index, existing)
                for index, existing in enumerate(notes)
                if existing.midi == note.midi
                and existing.start < core_start_seconds
                and existing.end >= global_start
            ]
            if candidates:
                target_index, target = max(candidates, key=lambda item: item[1].start)
                stitched_end = max(target.end, global_end)
                if stitched_end > target.end:
                    notes[target_index] = target.model_copy(
                        update={"duration": stitched_end - target.start}
                    )
            continue

        in_core = global_start >= core_start_seconds and (
            global_start < core_end_seconds or (is_last and global_start <= core_end_seconds)
        )
        if in_core:
            notes.append(note.model_copy(update={"start": global_start}))


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
        chunk_seconds: float = 45.0,
        overlap_seconds: float = 1.0,
    ) -> None:
        self.fmin_hz = fmin_hz
        self.fmax_hz = fmax_hz
        self.hop_length = hop_length
        self.minimum_note_seconds = minimum_note_seconds
        self.review_threshold = review_threshold
        self.chunk_seconds = chunk_seconds
        self.overlap_seconds = overlap_seconds

    @property
    def version(self) -> str | None:
        try:
            import librosa

            return librosa.__version__
        except ImportError:
            return None

    def _transcribe_segment(self, y, sr: int) -> list[NoteEvent]:
        import librosa
        import numpy as np

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
        return notes

    def transcribe(
        self,
        audio_path: Path,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> BassTranscription:
        try:
            import librosa
        except ImportError as exc:
            raise RuntimeError(
                "librosa transcription dependencies are not installed. "
                "Install with: pip install -e '.[beat]'"
            ) from exc

        def progress(percent: float, message: str) -> None:
            if progress_callback is not None:
                progress_callback(max(0.0, min(100.0, percent)), message)

        audio_path = audio_path.resolve()
        progress(0.0, "Loading normalized audio")
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        if y.size == 0:
            raise ValueError(f"Audio file is empty: {audio_path}")

        windows = _analysis_windows(
            len(y),
            int(sr),
            chunk_seconds=self.chunk_seconds,
            overlap_seconds=self.overlap_seconds,
        )
        notes: list[NoteEvent] = []
        total_windows = len(windows)

        for index, (context_start, core_start, core_end, context_end) in enumerate(windows, start=1):
            progress(
                5.0 + (index - 1) / max(1, total_windows) * 90.0,
                f"Pitch analysis chunk {index} of {total_windows}",
            )
            segment = y[context_start:context_end]
            context_offset_seconds = context_start / float(sr)
            core_start_seconds = core_start / float(sr)
            core_end_seconds = core_end / float(sr)
            is_last = index == total_windows

            _append_chunk_observations(
                notes,
                self._transcribe_segment(segment, int(sr)),
                context_offset_seconds=context_offset_seconds,
                core_start_seconds=core_start_seconds,
                core_end_seconds=core_end_seconds,
                is_last=is_last,
            )

        notes.sort(key=lambda note: note.start)
        progress(100.0, f"Bass transcription complete ({len(notes)} note events)")
        return BassTranscription(
            engine=self.name,
            engine_version=librosa.__version__,
            source_path=str(audio_path),
            sample_rate_hz=int(sr),
            notes=notes,
        )
