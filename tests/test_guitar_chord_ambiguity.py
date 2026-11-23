"""Canonical #796 slice 38: polyphonic chord ambiguity for Lead/Rhythm guitar.

Every audio sample is original synthetic signal. No licensed song, model,
separator, OS audio device, private path, or human laptop test is used.
"""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from rocksmith_cdlc_generator.guitar_chord_ambiguity import (
    CHORD_ONSET_TOLERANCE_SECONDS,
    ChordScreenedOnset,
    screen_guitar_chord_onset_ambiguity,
)
from rocksmith_cdlc_generator.guitar_onset_oracle import GuitarAttackEvidence
from tests.test_bass_attack_evidence import START, synth


@pytest.mark.parametrize("role", ["lead", "rhythm"])
def test_monophonic_note_is_not_flagged_ambiguous(role, tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    (screened,) = screen_guitar_chord_onset_ambiguity(role, wav, [(START, 1.5)])
    assert isinstance(screened, ChordScreenedOnset)
    assert screened.chord_group_size == 1
    assert not screened.chord_ambiguous
    # A real monophonic attack is promoted exactly as the underlying oracle
    # already proves it; this screen adds no confidence of its own.
    assert screened.evidence.independent_attack
    assert screened.independently_verified


@pytest.mark.parametrize("role", ["lead", "rhythm"])
def test_exact_duplicate_onset_is_a_chord_not_rejected_input(role, tmp_path):
    # Unlike guitar_onset_oracle.inspect_guitar_onset_oracle (which rejects a
    # duplicate claimed time as malformed input), a real chord legitimately
    # strikes multiple strings at the identical instant.
    wav = synth(tmp_path / "attack.wav", "onset")
    first, second = screen_guitar_chord_onset_ambiguity(
        role, wav, [(START, 1.5), (START, 1.5)],
    )
    for screened in (first, second):
        assert screened.chord_group_size == 2
        assert screened.chord_ambiguous
        # The shared attack measures strongly, but chord membership vetoes
        # promotion of either individual member note.
        assert screened.evidence.independent_attack
        assert not screened.independently_verified


def test_near_simultaneous_onsets_within_tolerance_are_grouped_as_chord(tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    spacing = CHORD_ONSET_TOLERANCE_SECONDS / 2
    assert spacing <= CHORD_ONSET_TOLERANCE_SECONDS
    results = screen_guitar_chord_onset_ambiguity(
        "lead", wav, [(START, 1.5), (START + spacing, 1.4)],
    )
    for screened in results:
        assert screened.chord_group_size == 2
        assert screened.chord_ambiguous
        assert not screened.independently_verified


def test_onsets_beyond_tolerance_are_not_grouped(tmp_path):
    # Same fixture and spacing already proven monophonic in
    # test_guitar_onset_oracle.test_oracle_requires_first_and_later_events_independently.
    wav = synth(tmp_path / "attack.wav", "onset")
    results = screen_guitar_chord_onset_ambiguity(
        "rhythm", wav, [(START, 1.5), (2.5, 0.3)],
    )
    assert [screened.chord_group_size for screened in results] == [1, 1]
    assert not any(screened.chord_ambiguous for screened in results)
    first, later = results
    assert first.evidence.independent_attack
    assert first.independently_verified
    # The synthetic "onset" tone has no second transient at 2.5s; it is
    # correctly unverified by the underlying oracle, not by this screen.
    assert not later.evidence.independent_attack
    assert not later.independently_verified


def test_grouping_anchors_to_earliest_member_not_a_rolling_chain(tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    tol = CHORD_ONSET_TOLERANCE_SECONDS
    # The second note is just inside tolerance of the anchor (one chord); the
    # third is just inside tolerance of the *second* note but clearly beyond
    # tolerance of the anchor. A rolling chain would wrongly merge all three
    # into one group instead of anchor-grouping the first two only.
    near = tol * 0.9
    results = screen_guitar_chord_onset_ambiguity(
        "lead", wav, [(START, 0.5), (START + near, 0.5), (START + 2 * near, 0.5)],
    )
    first, second, third = results
    assert first.chord_group_size == 2
    assert second.chord_group_size == 2
    assert first.chord_ambiguous
    assert second.chord_ambiguous
    assert third.chord_group_size == 1
    assert not third.chord_ambiguous


def test_results_preserve_input_order_and_count_for_unsorted_input(tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    events = [(2.5, 0.3), (START, 1.5)]
    results = screen_guitar_chord_onset_ambiguity("rhythm", wav, events)
    assert len(results) == len(events)
    # Second input event (START) is the earlier onset and is independently
    # verified monophonic; first input event (2.5) is the later, unverified one.
    assert results[0].chord_group_size == 1
    assert not results[0].independently_verified
    assert results[1].chord_group_size == 1
    assert results[1].independently_verified


@pytest.mark.parametrize("role", ["bass", "BASS", "Lead", "guitar", "", None])
def test_invalid_role_is_rejected(role, tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    with pytest.raises(ValueError, match="INVALID_GUITAR_ONSET_ORACLE_ROLE"):
        screen_guitar_chord_onset_ambiguity(role, wav, [(START, 1.5)])


@pytest.mark.parametrize("invalid_events", [
    [(-1, 1.5)], [(float("nan"), 1.5)], [(START, 0)], [(START, "fake")],
])
def test_invalid_timing_arguments_never_read_files(invalid_events, tmp_path):
    with pytest.raises(ValueError, match="INVALID_GUITAR_ATTACK_ONSET_ARGUMENT"):
        screen_guitar_chord_onset_ambiguity(
            "lead", tmp_path / "missing.wav", invalid_events,
        )


def test_empty_event_sequence_returns_empty_result(tmp_path):
    wav = synth(tmp_path / "attack.wav", "onset")
    assert screen_guitar_chord_onset_ambiguity("lead", wav, []) == ()


def test_chord_screened_onset_rejects_inconsistent_construction():
    evidence = GuitarAttackEvidence("lead", "no_attack")
    with pytest.raises(ValueError, match="INVALID_CHORD_GROUP_SIZE"):
        ChordScreenedOnset(evidence, 0, False)
    with pytest.raises(ValueError, match="INVALID_CHORD_AMBIGUOUS_SINGLE_NOTE_GROUP"):
        ChordScreenedOnset(evidence, 1, True)


def test_report_does_not_contain_private_path_or_claim_pitch_truth(tmp_path):
    wav = synth(tmp_path / "private-recording.wav", "onset")
    results = screen_guitar_chord_onset_ambiguity(
        "lead", wav, [(START, 1.5), (START, 1.5)],
    )
    dumped = json.dumps([
        {**asdict(screened.evidence), "chord_group_size": screened.chord_group_size,
         "chord_ambiguous": screened.chord_ambiguous}
        for screened in results
    ])
    assert "private-recording.wav" not in dumped
    assert str(tmp_path) not in dumped
    for screened in results:
        assert screened.evidence.pitch_verified is False
        assert screened.evidence.source_isolation_proven is False
        assert screened.evidence.recording_clock_verified is False
        assert screened.evidence.musical_pass_proven is False
