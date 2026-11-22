"""Canonical #796 slice 31: octave-correlated non-Bass sources cannot confirm E1.

Fully original synthetic PCM; no private music, model or human laptop step.
"""
from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import sys
import wave

import pytest

from rocksmith_cdlc_generator.alignment import (
    AlignmentAnchor, AlignmentRegion, AlignmentReport,
)
from rocksmith_cdlc_generator.bass_octave_negative import (
    inspect_bass_octave_leakage,
)
from rocksmith_cdlc_generator.instrument_audio_focus import midi_frequency
from rocksmith_cdlc_generator.reconciliation import reconcile_bass_sources
from rocksmith_cdlc_generator.source_import import (
    ImportedSource, SourceNoteEvent, SourceProvenance,
    SourceTempoEvent, SourceTrack, SourceTrustClass,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


RATE = 8000
E1 = midi_frequency(28)
E2 = 2 * E1
F1 = midi_frequency(29)


def synthetic_audio(path: Path, components: list[tuple[float, float]], *,
                    stereo_opposite: bool = False) -> Path:
    frames = array("h")
    for i in range(RATE * 3):
        instant = i / RATE
        val = round(sum(a * math.sin(2 * math.pi * f * instant)
                        for f, a in components))
        if stereo_opposite:
            frames.extend([val, -val])
        else:
            frames.append(val)
    if sys.byteorder != "little":
        frames.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2 if stereo_opposite else 1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(frames.tobytes())
    return path


def screen(path: Path, midi: int = 28, duration: float = 2.0):
    return inspect_bass_octave_leakage(
        path, expected_midi=midi,
        note_start_seconds=.40, note_duration_seconds=duration,
    )


def test_octave_only_e2_without_e1_fundamental_is_negative_in_both_windows(tmp_path):
    wave_path = synthetic_audio(tmp_path / "synthetic-e2-only.wav", [(E2, 7000)])
    result = screen(wave_path)
    assert result.status == "octave_leakage"
    assert result.observed_windows == 2
    assert result.must_veto
    assert result.bass_pitch_verified is False
    assert result.source_isolation_proven is False
    assert result.score_authority_changed is False


@pytest.mark.parametrize("components", [
    [(E1, 6400), (E2, 1700)],
    [(E1, 2800), (E2, 6800)],
    [(F1, 6200)],
])
def test_real_fundamental_or_unrelated_semitone_is_not_falsely_labeled_octave_leak(
    tmp_path, components,
):
    wav = synthetic_audio(tmp_path / "synthetic-control.wav", components)
    result = screen(wav)
    assert result.status == "not_detected"
    assert result.must_veto is False
    assert result.bass_pitch_verified is False


def test_unqualified_unknown_silence_short_notes_and_truncated_wave_never_positive(
    tmp_path,
):
    quiet = synthetic_audio(tmp_path / "synthetic-silence.wav", [])
    assert screen(quiet).status == "insufficient_signal"
    pure = synthetic_audio(tmp_path / "synthetic.wav", [(E2, 7000)])
    assert screen(pure, duration=.25).status == "insufficient_signal"
    assert screen(tmp_path / "absent.wav").status == "unavailable"
    pure.write_bytes(pure.read_bytes()[:-2])
    assert screen(pure).status == "unavailable"


def test_stereo_phase_reversal_retains_negative_e2_detection(tmp_path):
    wav = synthetic_audio(
        tmp_path / "synthetic-stereo.wav", [(E2, 7100)],
        stereo_opposite=True,
    )
    assert screen(wav).status == "octave_leakage"


@pytest.mark.parametrize("kwargs", [
    {"expected_midi": 128}, {"expected_midi": -1},
    {"expected_midi": True}, {"expected_midi": 28.0},
    {"note_start_seconds": -1}, {"note_start_seconds": float("nan")},
    {"note_duration_seconds": 0}, {"note_duration_seconds": float("inf")},
])
def test_invalid_midi_and_geometry_arguments_fail_before_audio_read(tmp_path, kwargs):
    args = dict(expected_midi=28, note_start_seconds=.4, note_duration_seconds=2.0)
    args.update(kwargs)
    with pytest.raises(ValueError, match="INVALID_BASS_OCTAVE_NEGATIVE_ARGUMENT"):
        inspect_bass_octave_leakage(tmp_path / "absent.wav", **args)


def _synthetic_score_alignment_and_note():
    provenance = SourceProvenance(
        source_type="midi", source_filename="fixture.mid",
        source_sha256="a"*64, importer="synthetic-test", importer_version="1",
    )
    source = ImportedSource(
        provenance=provenance,
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0, bpm=120)],
        tracks=[SourceTrack(
            source_track_index=0, name="Bass", instrument="bass",
            tuning_midi=[28, 33, 38, 43],
            notes=[SourceNoteEvent(
                start_seconds=.4, duration_seconds=2.0,
                midi=28, string_index=0, fret=0, import_confidence=1.0,
            )],
        )],
    )
    alignment = AlignmentReport(
        source_path="fixture.mid", source_sha256="a"*64, track_index=0,
        audio_beat_start_index=0, global_offset_seconds=0,
        anchor_stride_beats=1, matched_beats=2,
        rms_residual_seconds=0, median_abs_residual_seconds=0,
        max_abs_residual_seconds=0, confidence=1.0,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=x, audio_time_seconds=x,
                source_beat_index=i, audio_beat_index=i,
                confidence=1.0,
            )
            for i, x in enumerate((0.0, 3.0))
        ],
        regions=[AlignmentRegion(
            source_start_seconds=0, source_end_seconds=3,
            audio_start_seconds=0, audio_end_seconds=3,
            rms_residual_seconds=0, max_abs_residual_seconds=0,
            confidence=1.0,
        )],
    )
    confidence = NoteEvent(
        start=.4, duration=2.0, midi=28,
        confidence=1.0, pitch_confidence=1.0,
        timing_confidence=1.0,
    )
    audio = BassTranscription(
        engine="synthetic-perfect-not-a-real-pyin",
        source_path="synthetic.wav", sample_rate_hz=RATE, notes=[confidence],
    )
    return source, alignment, audio


def test_octave_only_source_vetoes_fake_perfect_note_even_with_upstream_proof_true(
    tmp_path,
):
    wav = synthetic_audio(tmp_path / "synthetic-e2.wav", [(E2, 7000)])
    source, alignment, audio = _synthetic_score_alignment_and_note()
    chart, review = reconcile_bass_sources(
        source, alignment, audio,
        verified_stem_provenance=True,
        octave_negative_probe=lambda midi, start, duration:
            inspect_bass_octave_leakage(
                wav, expected_midi=midi, note_start_seconds=start,
                note_duration_seconds=duration,
            ).status,
    )
    note = chart.notes[0]
    assert note.status == "verified_match"  # observational pitch match only
    assert note.trust_class == SourceTrustClass.symbolic_unverified
    assert note.review_required
    assert note.qualification_reasons == ["OCTAVE_LEAKAGE_NEGATIVE"]
    assert note.qualification_observations["octave_leakage_detected"] is True
    assert chart.audio_evidence_provenance == "verified_stem"
    assert not any(n.trust_class == SourceTrustClass.symbolic_verified
                   for n in chart.notes)
    # Review/diagnostics never contain private WAV paths or song material.
    assert str(wav) not in chart.model_dump_json()


def test_root_bearing_signal_cannot_gain_authority_from_negative_diagnostic(tmp_path):
    wav = synthetic_audio(tmp_path / "synthetic-bass.wav", [(E1, 6500), (E2, 1700)])
    source, alignment, audio = _synthetic_score_alignment_and_note()
    chart, _ = reconcile_bass_sources(
        source, alignment, audio,
        verified_stem_provenance=False,
        octave_negative_probe=lambda *_: (_ for _ in ()).throw(
            AssertionError("Never run octave probe on unverified stem")
        ),
    )
    note = chart.notes[0]
    assert note.trust_class == SourceTrustClass.symbolic_unverified
    assert note.qualification_reasons == ["UNVERIFIED_STEM"]
    assert screen(wav).status == "not_detected"


def test_unreadable_octave_probe_rejects_strong_matching_note():
    source, alignment, audio = _synthetic_score_alignment_and_note()
    chart, _ = reconcile_bass_sources(
        source, alignment, audio, verified_stem_provenance=True,
        octave_negative_probe=lambda *_: "unavailable",
    )
    assert chart.notes[0].qualification_reasons == ["OCTAVE_SCREEN_UNAVAILABLE"]
    assert chart.notes[0].review_required
    assert chart.notes[0].trust_class == SourceTrustClass.symbolic_unverified


def test_invalid_octave_probe_verdict_is_not_silent_success():
    source, alignment, audio = _synthetic_score_alignment_and_note()
    with pytest.raises(ValueError, match="INVALID_BASS_OCTAVE_NEGATIVE_STATUS"):
        reconcile_bass_sources(
            source, alignment, audio, verified_stem_provenance=True,
            octave_negative_probe=lambda *_: "imagined_pass",
        )
    with pytest.raises(ValueError, match="INVALID_BASS_OCTAVE_NEGATIVE_PROBE"):
        reconcile_bass_sources(
            source, alignment, audio, verified_stem_provenance=True,
            octave_negative_probe=True,
        )


def test_octave_negative_report_never_contains_private_identity(tmp_path):
    wav = synthetic_audio(tmp_path / "private-piece.wav", [(E2, 7000)])
    report = screen(wav)
    data = json.dumps(report.__dict__)
    assert "private-piece.wav" not in data
    assert "model" not in data
    assert "music" not in data
