from rocksmith_cdlc_generator.fret_mapping import map_bass_transcription
from rocksmith_cdlc_generator.fretboard import DROP_D, E_STANDARD, candidate_positions
from rocksmith_cdlc_generator.mapping_quality import review_bass_mapping
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


def make_transcription(midis: list[int]) -> BassTranscription:
    return BassTranscription(
        engine="test",
        source_path="synthetic.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(
                start=index * 0.5,
                duration=0.4,
                midi=midi,
                confidence=0.95,
                pitch_confidence=0.95,
                timing_confidence=0.95,
            )
            for index, midi in enumerate(midis)
        ],
    )


def test_candidate_positions_standard_e() -> None:
    positions = candidate_positions(40, E_STANDARD, max_fret=24)
    assert {(position.string, position.fret) for position in positions} == {
        (0, 12),
        (1, 7),
        (2, 2),
    }


def test_drop_d_exposes_low_d() -> None:
    assert candidate_positions(26, E_STANDARD) == []
    positions = candidate_positions(26, DROP_D)
    assert [(position.string, position.fret) for position in positions] == [(0, 0)]


def test_sequence_mapper_prefers_coherent_position() -> None:
    transcription = make_transcription([40, 42, 43, 45, 43, 42, 40])
    mapping = map_bass_transcription(transcription, E_STANDARD)
    assert mapping.unmapped_count == 0
    assert all(note.mapped for note in mapping.notes)
    jumps = [
        abs(current.fret - previous.fret)
        for previous, current in zip(mapping.notes, mapping.notes[1:])
        if previous.fret is not None and current.fret is not None
    ]
    assert max(jumps) <= 5


def test_unplayable_note_fails_review() -> None:
    transcription = make_transcription([20, 28])
    mapping = map_bass_transcription(transcription, E_STANDARD)
    review = review_bass_mapping(mapping)
    assert mapping.unmapped_count == 1
    assert review.status == "FAIL"


def test_mapping_preserves_source_review_flag() -> None:
    transcription = make_transcription([40])
    transcription.notes[0].review_required = True
    mapping = map_bass_transcription(transcription, E_STANDARD)
    assert mapping.notes[0].review_required is True
