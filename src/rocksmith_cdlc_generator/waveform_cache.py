from __future__ import annotations

from array import array
from pathlib import Path
import wave

from pydantic import BaseModel, ConfigDict, Field

from .hashing import sha256_file
from .models import ProjectManifest


class WaveformEnvelope(BaseModel):
    """Compact peak envelope for responsive Song Workspace rendering."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_rate_hz: int = Field(gt=0)
    channels: int = Field(gt=0)
    frames: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    bucket_frames: int = Field(gt=0)
    minimums: list[float]
    maximums: list[float]

    @property
    def bucket_count(self) -> int:
        return len(self.minimums)


def normalized_audio_path(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    manifest = ProjectManifest.load(project)
    output = manifest.normalized_audio.output
    if manifest.normalized_audio.status != "complete" or output is None:
        raise FileNotFoundError("Normalized project audio is not available yet")
    path = (project / output.path).resolve()
    if not path.is_relative_to(project) or not path.is_file():
        raise FileNotFoundError("Normalized project audio is missing")
    if sha256_file(path) != output.sha256:
        raise ValueError("Normalized project audio content no longer matches the project manifest")
    return path


def _read_pcm16_mono_peak_samples(path: Path, *, target_buckets: int) -> WaveformEnvelope:
    if target_buckets < 100:
        raise ValueError("target_buckets must be at least 100")

    audio_sha = sha256_file(path)
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_rate = source.getframerate()
        sample_width = source.getsampwidth()
        frames = source.getnframes()
        compression = source.getcomptype()
        if sample_width != 2 or compression != "NONE":
            raise ValueError("Waveform preview requires uncompressed 16-bit PCM normalized audio")
        if channels < 1:
            raise ValueError("Normalized audio has no channels")
        if frames < 1:
            raise ValueError("Normalized audio is empty")

        bucket_frames = max(1, (frames + target_buckets - 1) // target_buckets)
        minimums: list[float] = []
        maximums: list[float] = []
        scale = 32768.0

        while True:
            payload = source.readframes(bucket_frames)
            if not payload:
                break
            values = array("h")
            values.frombytes(payload)
            if not values:
                break
            # Normalize to one display envelope by averaging absolute channel energy per frame
            # while preserving sign from the channel-average sample.
            low = 1.0
            high = -1.0
            frame_count = len(values) // channels
            for frame_index in range(frame_count):
                base = frame_index * channels
                sample = sum(values[base + channel] for channel in range(channels)) / channels
                normalized = max(-1.0, min(1.0, sample / scale))
                low = min(low, normalized)
                high = max(high, normalized)
            minimums.append(low if low <= high else 0.0)
            maximums.append(high if high >= low else 0.0)

    return WaveformEnvelope(
        audio_sha256=audio_sha,
        sample_rate_hz=sample_rate,
        channels=channels,
        frames=frames,
        duration_seconds=frames / sample_rate,
        bucket_frames=bucket_frames,
        minimums=minimums,
        maximums=maximums,
    )


def load_or_build_waveform(project_dir: Path, *, target_buckets: int = 5000) -> WaveformEnvelope:
    """Return a cached waveform envelope tied to the exact normalized audio bytes."""

    project = project_dir.expanduser().resolve()
    audio = normalized_audio_path(project)
    audio_sha = sha256_file(audio)
    cache_path = project / "analysis" / "waveform.json"
    if cache_path.is_file():
        try:
            cached = WaveformEnvelope.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if cached is not None and cached.audio_sha256 == audio_sha:
            return cached

    envelope = _read_pcm16_mono_peak_samples(audio, target_buckets=target_buckets)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(envelope.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return envelope
