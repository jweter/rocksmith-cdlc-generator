from __future__ import annotations

from pathlib import Path
import threading
import wave

from .waveform_cache import normalized_audio_path


class PlaybackUnavailable(RuntimeError):
    pass


class ProjectAudioTransport:
    """Thread-safe transport for the deterministic normalized project WAV.

    The backend is deliberately local and minimal. It never invokes a shell, never
    downloads media, and never mutates project audio. `sounddevice` is imported lazily so
    non-desktop/core workflows do not require an audio device.
    """

    def __init__(self, project_dir: Path) -> None:
        self.project = project_dir.expanduser().resolve()
        self.audio_path = normalized_audio_path(self.project)
        self._lock = threading.RLock()
        self._stream = None
        self._wave: wave.Wave_read | None = None
        self._position_frames = 0
        self._playing = False
        self._closed = False

        with wave.open(str(self.audio_path), "rb") as source:
            self.sample_rate_hz = source.getframerate()
            self.channels = source.getnchannels()
            self.sample_width = source.getsampwidth()
            self.total_frames = source.getnframes()
            compression = source.getcomptype()
        if self.sample_width != 2 or compression != "NONE":
            raise PlaybackUnavailable("Playback requires the normalized 16-bit PCM WAV")
        if self.channels < 1 or self.sample_rate_hz <= 0 or self.total_frames <= 0:
            raise PlaybackUnavailable("Normalized audio metadata is invalid")

    @property
    def duration_seconds(self) -> float:
        return self.total_frames / self.sample_rate_hz

    @property
    def playing(self) -> bool:
        with self._lock:
            return self._playing

    @property
    def position_seconds(self) -> float:
        with self._lock:
            return min(self._position_frames, self.total_frames) / self.sample_rate_hz

    def _require_sounddevice(self):
        try:
            import sounddevice as sd
        except Exception as exc:  # pragma: no cover - depends on local audio runtime
            raise PlaybackUnavailable(
                "Desktop audio playback is unavailable. Install/enable the sounddevice runtime "
                "or choose a working Windows output device."
            ) from exc
        return sd

    def _open_wave_at_position(self) -> wave.Wave_read:
        source = wave.open(str(self.audio_path), "rb")
        source.setpos(min(self._position_frames, self.total_frames))
        return source

    def _callback(self, outdata, frames: int, _time_info, _status) -> None:
        with self._lock:
            if not self._playing or self._wave is None:
                outdata[:] = b"\x00" * len(outdata)
                return
            payload = self._wave.readframes(frames)
            expected = frames * self.channels * self.sample_width
            actual_frames = len(payload) // (self.channels * self.sample_width)
            self._position_frames = min(self.total_frames, self._position_frames + actual_frames)
            if len(payload) < expected:
                payload += b"\x00" * (expected - len(payload))
                self._playing = False
            outdata[:] = payload

    def play(self) -> None:
        with self._lock:
            if self._closed:
                raise PlaybackUnavailable("Playback transport is closed")
            if self._position_frames >= self.total_frames:
                self._position_frames = 0
            if self._wave is not None:
                self._wave.close()
            self._wave = self._open_wave_at_position()
            sd = self._require_sounddevice()
            if self._stream is None:
                self._stream = sd.RawOutputStream(
                    samplerate=self.sample_rate_hz,
                    channels=self.channels,
                    dtype="int16",
                    callback=self._callback,
                    blocksize=0,
                )
                self._stream.start()
            elif not self._stream.active:
                self._stream.start()
            self._playing = True

    def pause(self) -> None:
        with self._lock:
            self._playing = False

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            self._position_frames = 0
            if self._wave is not None:
                self._wave.close()
                self._wave = None

    def seek(self, seconds: float) -> None:
        if seconds != seconds:  # NaN guard
            raise ValueError("seek position must be a number")
        bounded = min(max(float(seconds), 0.0), self.duration_seconds)
        with self._lock:
            was_playing = self._playing
            self._position_frames = min(self.total_frames, int(round(bounded * self.sample_rate_hz)))
            if self._wave is not None:
                self._wave.close()
                self._wave = None
            if was_playing and self._position_frames < self.total_frames:
                self._wave = self._open_wave_at_position()
            elif self._position_frames >= self.total_frames:
                self._playing = False

    def close(self) -> None:
        with self._lock:
            self._playing = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                finally:
                    self._stream.close()
                self._stream = None
            if self._wave is not None:
                self._wave.close()
                self._wave = None
            self._closed = True
