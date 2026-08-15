from __future__ import annotations

from array import array
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.audio_playback import ProjectAudioTransport
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import ArtifactRecord, AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.waveform_cache import load_or_build_waveform, normalized_audio_path


def _project_with_normalized_audio(tmp_path: Path, *, seconds: float = 1.0) -> Path:
    project = tmp_path / "song"
    (project / "audio").mkdir(parents=True)
    (project / "analysis").mkdir()
    (project / "source").mkdir()

    source = project / "source" / "source.wav"
    source.write_bytes(b"source-placeholder")

    sample_rate = 44100
    frames = int(sample_rate * seconds)
    normalized = project / "audio" / "normalized.wav"
    samples = array("h")
    for index in range(frames):
        # Deterministic low-amplitude square wave in stereo.
        value = 12000 if (index // 100) % 2 == 0 else -12000
        samples.extend((value, value))
    with wave.open(str(normalized), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(samples.tobytes())

    manifest = ProjectManifest(
        project_name="Example - Song",
        artist="Example",
        title="Song",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path=str(source),
        source_project_path="source/source.wav",
        source_sha256="1" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=seconds,
            sample_rate_hz=sample_rate,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )
    manifest.normalized_audio.status = "complete"
    manifest.normalized_audio.output = ArtifactRecord(
        path="audio/normalized.wav",
        sha256=sha256_file(normalized),
    )
    manifest.save(project)
    return project


def test_waveform_cache_is_bound_to_normalized_audio(tmp_path: Path) -> None:
    project = _project_with_normalized_audio(tmp_path)
    envelope = load_or_build_waveform(project, target_buckets=200)

    assert envelope.audio_sha256 == sha256_file(project / "audio" / "normalized.wav")
    assert envelope.sample_rate_hz == 44100
    assert envelope.channels == 2
    assert envelope.bucket_count > 0
    assert min(envelope.minimums) < 0
    assert max(envelope.maximums) > 0
    assert (project / "analysis" / "waveform.json").is_file()

    cached = load_or_build_waveform(project, target_buckets=200)
    assert cached == envelope


def test_normalized_audio_path_rejects_changed_bytes(tmp_path: Path) -> None:
    project = _project_with_normalized_audio(tmp_path)
    normalized = project / "audio" / "normalized.wav"
    normalized.write_bytes(normalized.read_bytes() + b"changed")

    with pytest.raises(ValueError, match="no longer matches"):
        normalized_audio_path(project)


def test_project_audio_transport_seek_does_not_require_audio_device(tmp_path: Path) -> None:
    project = _project_with_normalized_audio(tmp_path, seconds=2.0)
    transport = ProjectAudioTransport(project)
    try:
        assert transport.duration_seconds == pytest.approx(2.0, abs=0.001)
        assert transport.position_seconds == pytest.approx(0.0)

        transport.seek(1.25)
        assert transport.position_seconds == pytest.approx(1.25, abs=1 / 44100)

        transport.seek(-5)
        assert transport.position_seconds == pytest.approx(0.0)

        transport.seek(99)
        assert transport.position_seconds == pytest.approx(2.0, abs=1 / 44100)

        transport.stop()
        assert transport.position_seconds == pytest.approx(0.0)
    finally:
        transport.close()
