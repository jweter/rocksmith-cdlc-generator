from __future__ import annotations

from array import array
from pathlib import Path
import math
import threading
import wave

from .waveform_cache import normalized_audio_path


class PlaybackUnavailable(RuntimeError):
    pass


class ProjectAudioTransport:
    """Thread-safe transport for the deterministic normalized project WAV."""

    def __init__(self, project_dir: Path) -> None:
        self.project = project_dir.expanduser().resolve()
        self.audio_path = normalized_audio_path(self.project)
        self._lock = threading.RLock()
        self._stream = None
        self._wave: wave.Wave_read | None = None
        self._position_frames = 0
        self._playing = False
        self._closed = False
        self._rate = 1.0
        self._loop_start_frames: int | None = None
        self._loop_end_frames: int | None = None
        self._click_enabled = False
        self._click_frames: tuple[int, ...] = ()

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

    @property
    def playback_rate(self) -> float:
        with self._lock:
            return self._rate

    @property
    def loop_range(self) -> tuple[float, float] | None:
        with self._lock:
            if self._loop_start_frames is None or self._loop_end_frames is None:
                return None
            return (
                self._loop_start_frames / self.sample_rate_hz,
                self._loop_end_frames / self.sample_rate_hz,
            )

    def _require_sounddevice(self):
        try:
            import sounddevice as sd
        except Exception as exc:  # pragma: no cover
            raise PlaybackUnavailable(
                "Desktop audio playback is unavailable. Install/enable the sounddevice runtime "
                "or choose a working Windows output device."
            ) from exc
        return sd

    def _open_wave_at_position(self) -> wave.Wave_read:
        source = wave.open(str(self.audio_path), "rb")
        source.setpos(min(self._position_frames, self.total_frames))
        return source

    def _mix_click(self, payload: bytes, start_frame: int, actual_frames: int) -> bytes:
        if not self._click_enabled or not self._click_frames or actual_frames <= 0:
            return payload
        samples = array("h")
        samples.frombytes(payload)
        click_length = max(1, int(self.sample_rate_hz * 0.025))
        block_end = start_frame + actual_frames
        for click_frame in self._click_frames:
            if click_frame >= block_end:
                break
            if click_frame + click_length <= start_frame:
                continue
            first = max(click_frame, start_frame)
            last = min(click_frame + click_length, block_end)
            for frame in range(first, last):
                phase = (frame - click_frame) / self.sample_rate_hz
                envelope = 1.0 - ((frame - click_frame) / click_length)
                click = int(9000 * envelope * math.sin(2.0 * math.pi * 1200.0 * phase))
                relative = frame - start_frame
                for channel in range(self.channels):
                    index = relative * self.channels + channel
                    value = samples[index] + click
                    samples[index] = max(-32768, min(32767, value))
        return samples.tobytes()

    def _callback(self, outdata, frames: int, _time_info, _status) -> None:
        with self._lock:
            if not self._playing or self._wave is None:
                outdata[:] = b"\x00" * len(outdata)
                return

            if (
                self._loop_start_frames is not None
                and self._loop_end_frames is not None
                and self._position_frames >= self._loop_end_frames
            ):
                self._position_frames = self._loop_start_frames
                self._wave.close()
                self._wave = self._open_wave_at_position()

            requested = frames
            if self._loop_end_frames is not None:
                requested = min(requested, max(0, self._loop_end_frames - self._position_frames))
                if requested == 0 and self._loop_start_frames is not None:
                    self._position_frames = self._loop_start_frames
                    self._wave.close()
                    self._wave = self._open_wave_at_position()
                    requested = frames

            start_frame = self._position_frames
            payload = self._wave.readframes(requested)
            actual_frames = len(payload) // (self.channels * self.sample_width)
            payload = self._mix_click(payload, start_frame, actual_frames)
            self._position_frames = min(self.total_frames, self._position_frames + actual_frames)

            if self._loop_end_frames is not None and self._position_frames >= self._loop_end_frames:
                if self._loop_start_frames is not None:
                    self._position_frames = self._loop_start_frames
                    self._wave.close()
                    self._wave = self._open_wave_at_position()
            elif self._position_frames >= self.total_frames:
                self._playing = False

            expected = frames * self.channels * self.sample_width
            if len(payload) < expected:
                payload += b"\x00" * (expected - len(payload))
            outdata[:] = payload

    def _new_stream(self):
        sd = self._require_sounddevice()
        return sd.RawOutputStream(
            samplerate=max(8000, int(round(self.sample_rate_hz * self._rate))),
            channels=self.channels,
            dtype="int16",
            callback=self._callback,
            blocksize=0,
        )

    def _detach_stream(self):
        with self._lock:
            stream = self._stream
            self._stream = None
            return stream

    @staticmethod
    def _shutdown_stream(stream) -> None:
        if stream is None:
            return
        try:
            if getattr(stream, "active", False):
                stream.stop()
        finally:
            stream.close()

    def play(self) -> None:
        with self._lock:
            if self._closed:
                raise PlaybackUnavailable("Playback transport is closed")
            if self._position_frames >= self.total_frames:
                self._position_frames = 0
            if self._wave is not None:
                self._wave.close()
            self._wave = self._open_wave_at_position()
            if self._stream is None:
                self._stream = self._new_stream()
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
            self._position_frames = self._loop_start_frames or 0
            if self._wave is not None:
                self._wave.close()
                self._wave = None

    def seek(self, seconds: float) -> None:
        if seconds != seconds:
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

    def set_playback_rate(self, rate: float) -> None:
        if rate not in {0.5, 0.75, 1.0}:
            raise ValueError("playback rate must be 0.5, 0.75, or 1.0")
        with self._lock:
            if self._rate == rate:
                return
            was_playing = self._playing
            self._playing = False
            self._rate = rate
        stream = self._detach_stream()
        self._shutdown_stream(stream)
        if was_playing:
            self.play()

    def set_loop(self, start_seconds: float, end_seconds: float) -> None:
        if start_seconds < 0 or end_seconds <= start_seconds or end_seconds > self.duration_seconds + 1e-6:
            raise ValueError("loop range must be inside the song and have positive duration")
        with self._lock:
            self._loop_start_frames = int(round(start_seconds * self.sample_rate_hz))
            self._loop_end_frames = int(round(end_seconds * self.sample_rate_hz))
            if not (self._loop_start_frames <= self._position_frames < self._loop_end_frames):
                self._position_frames = self._loop_start_frames
                if self._wave is not None:
                    self._wave.close()
                    self._wave = self._open_wave_at_position()

    def clear_loop(self) -> None:
        with self._lock:
            self._loop_start_frames = None
            self._loop_end_frames = None

    def configure_click(self, beat_times: list[float] | tuple[float, ...], *, enabled: bool) -> None:
        frames = tuple(
            sorted(
                int(round(time_seconds * self.sample_rate_hz))
                for time_seconds in beat_times
                if 0 <= time_seconds <= self.duration_seconds
            )
        )
        with self._lock:
            self._click_frames = frames
            self._click_enabled = enabled

    def close(self) -> None:
        with self._lock:
            self._playing = False
            stream = self._stream
            self._stream = None
            wave_source = self._wave
            self._wave = None
            self._closed = True
        # PortAudio stop/close can wait for the callback. Never hold the callback lock here.
        self._shutdown_stream(stream)
        if wave_source is not None:
            wave_source.close()
