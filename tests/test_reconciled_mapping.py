from rocksmith_cdlc_generator.fret_mapping import map_reconciled_bass_chart
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.reconciliation import ReconciledBassChart, ReconciledBassNote
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(**updates):
    data = dict(
        start_seconds=1.0,
        duration_seconds=0.5,
        midi=31,
        string_index=0,
        fret=3,
        techniques=["palm_mute"],
        status="verified_match",
        trust_class=SourceTrustClass.symbolic_verified,
        review_required=False,
        symbolic_start_seconds=0.0,
        audio_start_seconds=1.01,
        onset_delta_seconds=0.01,
        symbolic_midi=31,
        audio_midi=31,
        symbolic_import_confidence=1.0,
        audio_confidence=0.95,
        alignment_confidence=0.95,
    )
    data.update(updates)
    return ReconciledBassNote(**data)


def test_preserves_verified_symbolic_fingering_and_techniques() -> None:
    chart = ReconciledBassChart(
        source_sha256="a" * 64,
        track_index=2,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[_note()],
    )
    mapping = map_reconciled_bass_chart(chart, E_STANDARD)
    note = mapping.notes[0]
    assert (note.string, note.fret) == (0, 3)
    assert note.position_source == "symbolic"
    assert note.mapping_confidence == 1.0
    assert note.techniques == ["palm_mute"]
    assert note.trust_class == SourceTrustClass.symbolic_verified
    assert note.review_required is False


def test_invalid_symbolic_position_is_not_locked() -> None:
    chart = ReconciledBassChart(
        source_sha256="b" * 64,
        track_index=2,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[_note(fret=5)],
    )
    mapping = map_reconciled_bass_chart(chart, E_STANDARD)
    note = mapping.notes[0]
    assert note.position_source == "inferred"
    assert (note.string, note.fret) != (0, 5)
    assert note.review_required is True


def test_unfingered_reconciled_note_uses_inference() -> None:
    chart = ReconciledBassChart(
        source_sha256="c" * 64,
        track_index=2,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[_note(string_index=None, fret=None)],
    )
    mapping = map_reconciled_bass_chart(chart, E_STANDARD)
    note = mapping.notes[0]
    assert note.mapped
    assert note.position_source == "inferred"


def test_audio_only_detection_remains_review_evidence_not_mapped_chart_content() -> None:
    chart = ReconciledBassChart(
        source_sha256="d" * 64,
        track_index=2,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=[
            _note(),
            _note(
                start_seconds=2.0,
                midi=12,
                string_index=None,
                fret=None,
                techniques=[],
                status="audio_only",
                trust_class=SourceTrustClass.audio_derived,
                review_required=True,
                symbolic_start_seconds=None,
                audio_start_seconds=2.0,
                onset_delta_seconds=None,
                symbolic_midi=None,
                audio_midi=12,
                symbolic_import_confidence=None,
                audio_confidence=0.90,
            ),
        ],
    )

    mapping = map_reconciled_bass_chart(chart, E_STANDARD)

    assert len(chart.notes) == 2
    assert len(mapping.notes) == 1
    assert mapping.notes[0].midi == 31
    assert mapping.notes[0].mapped
