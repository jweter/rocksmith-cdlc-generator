from __future__ import annotations

from array import array
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.audio_playback import ProjectAudioTransport
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import ArtifactRecord, AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.timing_review import (
    load_reviewed_timing,
    nudge_reviewed_beat,
    promote_reviewed_timing,
    refit_between_locked_anchors,
    set_anchor_locked,
    set_reviewed_beat_time,
)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "song"
    for relative in ("audio", "analysis", "source", "review"):
        (project / relative).mkdir(parents=True, exist_ok=True)
    source = project / "source" / "source.wav"
    source.write_bytes(b"source")
    normalized = project / "audio" / "normalized.wav"
    samples = array("h", [0, 0] * (44100 * 3))
    with wave.open(str(normalized), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(samples.tobytes())
    manifest = ProjectManifest(
        project_name="Timing Song",
        title="Timing Song",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path=str(source),
        source_project_path="source/source.wav",
        source_sha256="2" * 64,
        source_metadata=AudioMetadata(duration_seconds=3.0, sample_rate_hz=44100, channels=2),
    )
    manifest.normalized_audio.status = "complete"
    manifest.normalized_audio.output = ArtifactRecord(path="audio/normalized.wav", sha256=sha256_file(normalized))
    manifest.save(project)
    write_tempo_map(
        TempoMap(
            engine="fixture",
            beats=[
                BeatEvent(time=0.0, beat=1, measure=1, bpm=120, confidence=0.8, is_downbeat=True),
                BeatEvent(time=0.5, beat=2, measure=1, bpm=120, confidence=0.8),
                BeatEvent(time=1.0, beat=3, measure=1, bpm=120, confidence=0.8),
                BeatEvent(time=1.5, beat=4, measure=1, bpm=120, confidence=0.8),
                BeatEvent(time=2.0, beat=1, measure=2, bpm=120, confidence=0.8, is_downbeat=True),
            ],
        ),
        project / "analysis" / "tempo_map.json",
    )
    return project


def test_reviewed_timing_preserves_raw_and_refits_between_locks(tmp_path: Path) -> None:
    project = _project(tmp_path)
    original = (project / "analysis" / "tempo_map.json").read_bytes()
    review = load_reviewed_timing(project, create=True)
    assert review.anchors[2].reviewed_time_seconds == pytest.approx(1.0)

    set_anchor_locked(project, 0, True)
    set_reviewed_beat_time(project, 4, 2.2)
    set_anchor_locked(project, 4, True)
    review = refit_between_locked_anchors(project, 2)

    assert [anchor.reviewed_time_seconds for anchor in review.anchors] == pytest.approx([0.0, 0.55, 1.1, 1.65, 2.2])
    assert (project / "analysis" / "tempo_map.json").read_bytes() == original


def test_nudge_clears_confirmation_and_promotion_writes_separate_map(tmp_path: Path) -> None:
    project = _project(tmp_path)
    load_reviewed_timing(project, create=True)
    set_anchor_locked(project, 0, True)
    review, output = promote_reviewed_timing(project)
    assert review.human_confirmed is True
    assert output == project / "analysis" / "reviewed_tempo_map.json"

    changed = nudge_reviewed_beat(project, 1, 0.010)
    assert changed.human_confirmed is False
    assert changed.anchors[1].reviewed_time_seconds == pytest.approx(0.510)


def test_transport_loop_rate_click_and_close_without_audio_device(tmp_path: Path) -> None:
    project = _project(tmp_path)
    transport = ProjectAudioTransport(project)
    transport.set_loop(0.5, 1.5)
    assert transport.loop_range == pytest.approx((0.5, 1.5))
    transport.seek(2.5)
    transport.set_loop(0.5, 1.5)
    assert transport.position_seconds == pytest.approx(0.5, abs=1 / 44100)
    transport.set_playback_rate(0.75)
    assert transport.playback_rate == pytest.approx(0.75)
    transport.configure_click([0.0, 0.5, 1.0], enabled=True)
    transport.clear_loop()
    assert transport.loop_range is None
    transport.close()


def test_transport_rejects_invalid_review_controls(tmp_path: Path) -> None:
    transport = ProjectAudioTransport(_project(tmp_path))
    try:
        with pytest.raises(ValueError, match="playback rate"):
            transport.set_playback_rate(0.9)
        with pytest.raises(ValueError, match="loop range"):
            transport.set_loop(1.0, 0.5)
    finally:
        transport.close()
