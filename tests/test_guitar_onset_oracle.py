"""Canonical #796 slices 40/41: independent PCM onset oracle for Lead/Rhythm.

Every audio sample is original synthetic signal. No licensed song, model,
separator, OS audio device, private path, or human laptop test is used.
"""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from rocksmith_cdlc_generator.bass_attack_evidence import BassAttackEvidence
from rocksmith_cdlc_generator.guitar_onset_oracle import (
    GuitarAttackEvidence,
    GuitarOnsetOracleReport,
    inspect_guitar_attack_onset,
    inspect_guitar_onset_oracle,
)
from tests.test_bass_attack_evidence import START, synth


@pytest.mark.parametrize("role", ["lead", "rhythm"])
@pytest.mark.parametrize("kind", ["onset", "late40", "masked_edge70"])
def test_measured_pcm_attack_qualifies_for_each_non_bass_role(role, kind, tmp_path):
    wav = synth(tmp_path / "attack.wav", kind)
    result = inspect_guitar_attack_onset(
        role, wav, note_start_seconds=START, note_duration_seconds=1.5,
    )
    assert result.role == role
    assert result.status == "attack_detected"
    assert result.independent_attack
    assert result.confidence >= .60
    assert 0 <= result.measured_onset_delta_seconds <= .08
    assert result.post_attack_rms > result.pre_attack_rms
    assert not result.pitch_verified
    assert not result.source_isolation_proven
    assert not result.recording_clock_verified
    assert not result.musical_pass_proven


@pytest.mark.parametrize("role", ["lead", "rhythm"])
@pytest.mark.parametrize("kind", ["silent", "dc", "steady", "late110"])
def test_no_independent_onset_for_continuous_tone_dc_or_silence(role, kind, tmp_path):
    wav = synth(tmp_path / (kind + ".wav"), kind)
    result = inspect_guitar_attack_onset(
        role, wav, note_start_seconds=START, note_duration_seconds=1.5,
    )
    assert result.status == "no_attack"
    assert not result.independent_attack
    assert result.confidence == 0.0
    assert result.measured_onset_delta_seconds is None


def test_lead_and_rhythm_are_not_conflated_with_each_other_or_bass(tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    lead = inspect_guitar_attack_onset(
        "lead", wav, note_start_seconds=START, note_duration_seconds=1.5,
    )
    rhythm = inspect_guitar_attack_onset(
        "rhythm", wav, note_start_seconds=START, note_duration_seconds=1.5,
    )
    assert lead.role == "lead"
    assert rhythm.role == "rhythm"
    assert lead != rhythm
    assert not isinstance(lead, BassAttackEvidence)
    assert not isinstance(rhythm, BassAttackEvidence)
    assert not isinstance(BassAttackEvidence("attack_detected"), GuitarAttackEvidence)


@pytest.mark.parametrize("role", ["bass", "BASS", "Lead", "guitar", "", None])
def test_invalid_role_is_rejected_for_evidence_and_oracle(role, tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    with pytest.raises(ValueError, match="INVALID_GUITAR_ONSET_ORACLE_ROLE"):
        inspect_guitar_attack_onset(
            role, wav, note_start_seconds=START, note_duration_seconds=1.5,
        )
    with pytest.raises(ValueError, match="INVALID_GUITAR_ONSET_ORACLE_ROLE"):
        inspect_guitar_onset_oracle(role, wav, [(START, 1.5)])
    with pytest.raises(ValueError, match="role must be 'lead' or 'rhythm'"):
        GuitarAttackEvidence(role, "attack_detected")


@pytest.mark.parametrize("invalid", [
    {"note_start_seconds": -1}, {"note_start_seconds": float("nan")},
    {"note_duration_seconds": 0}, {"note_duration_seconds": "fake"},
])
def test_invalid_timing_arguments_never_read_files(invalid, tmp_path):
    args = {"note_start_seconds": START, "note_duration_seconds": 1.5}
    args.update(invalid)
    with pytest.raises(ValueError, match="INVALID_GUITAR_ATTACK_ONSET_ARGUMENT"):
        inspect_guitar_attack_onset("lead", tmp_path / "missing.wav", **args)


def test_oracle_requires_first_and_later_events_independently(tmp_path):
    # The synthetic "onset" tone sustains without a second transient, so a
    # later sample window inside the steady tail correctly reports no_attack.
    wav = synth(tmp_path / "attack.wav", "onset")
    report = inspect_guitar_onset_oracle(
        "lead", wav, [(START, 1.5), (2.5, 0.3)],
    )
    assert isinstance(report, GuitarOnsetOracleReport)
    assert report.role == "lead"
    assert len(report.events) == 2
    assert report.first_event_verified
    assert not report.later_events_verified
    assert report.verified_event_count == 1
    assert report.unverified_event_count == 1


def test_oracle_passes_only_when_every_claimed_event_is_independently_verified(tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    report = inspect_guitar_onset_oracle("rhythm", wav, [(START, 1.5)])
    assert report.first_event_verified
    # A single-event chart has no later event to independently confirm.
    assert not report.later_events_verified
    assert report.verified_event_count == 1
    assert report.unverified_event_count == 0


def test_oracle_rejects_unsorted_or_duplicate_time_event_sequences(tmp_path):
    # Reviewer-reproduced: reversing a two-event sequence must not silently
    # relabel which claimed onset is treated as "first".
    wav = synth(tmp_path / "attack.wav", "onset")
    with pytest.raises(
        ValueError, match="INVALID_GUITAR_ONSET_ORACLE_SEQUENCE_NOT_STRICTLY_ORDERED",
    ):
        inspect_guitar_onset_oracle("lead", wav, [(2.5, 0.3), (START, 1.5)])
    with pytest.raises(
        ValueError, match="INVALID_GUITAR_ONSET_ORACLE_SEQUENCE_NOT_STRICTLY_ORDERED",
    ):
        inspect_guitar_onset_oracle("rhythm", wav, [(START, 1.5), (START, 1.5)])


def test_report_does_not_contain_private_path_or_claim_pitch_truth(tmp_path):
    wav = synth(tmp_path / "private-recording.wav", "onset")
    report = inspect_guitar_onset_oracle("lead", wav, [(START, 1.5)])
    dumped = json.dumps([asdict(event) for event in report.events])
    assert "private-recording.wav" not in dumped
    assert str(tmp_path) not in dumped
    for event in report.events:
        assert event.pitch_verified is False
        assert event.recording_clock_verified is False
        assert event.musical_pass_proven is False
