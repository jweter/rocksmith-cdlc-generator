import json
from pathlib import Path

from rocksmith_cdlc_generator.fret_mapping import (
    BassMapping,
    MappedNote,
    bass_mapping_is_current,
    map_bass_transcription,
    write_bass_mapping,
)
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


def _sample_mapping() -> BassMapping:
    return BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[MappedNote(start=0.0, duration=0.4, midi=40, string=0, fret=12, source_confidence=0.9, mapping_confidence=0.9)],
    )


def test_freshly_written_mapping_is_current(tmp_path: Path) -> None:
    destination = tmp_path / "bass_mapped.json"
    write_bass_mapping(_sample_mapping(), destination)
    assert bass_mapping_is_current(destination) is True


def test_mapping_missing_algorithm_version_field_is_stale(tmp_path: Path) -> None:
    """A file written before mapping_algorithm_version existed must fail closed as stale.

    Regression coverage for #304/#193: a downstream artifact must never be silently
    treated as current authority just because it exists on disk.
    """
    destination = tmp_path / "bass_mapped.json"
    payload = _sample_mapping().model_dump(mode="json")
    del payload["mapping_algorithm_version"]
    destination.write_text(json.dumps(payload), encoding="utf-8")
    assert bass_mapping_is_current(destination) is False


def test_mapping_with_older_algorithm_version_is_stale(tmp_path: Path) -> None:
    destination = tmp_path / "bass_mapped.json"
    payload = _sample_mapping().model_dump(mode="json")
    payload["mapping_algorithm_version"] = 1
    destination.write_text(json.dumps(payload), encoding="utf-8")
    assert bass_mapping_is_current(destination) is False


def test_missing_mapping_file_is_not_current(tmp_path: Path) -> None:
    assert bass_mapping_is_current(tmp_path / "does_not_exist.json") is False
