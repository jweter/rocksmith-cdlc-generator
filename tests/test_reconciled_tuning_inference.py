from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.mapping_pipeline import _infer_reconciled_bass_tuning
from rocksmith_cdlc_generator.reconciliation import ReconciledBassChart, ReconciledBassNote
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(*, string_index: int, fret: int, midi: int) -> ReconciledBassNote:
    return ReconciledBassNote(
        start_seconds=float(string_index),
        duration_seconds=0.25,
        midi=midi,
        string_index=string_index,
        fret=fret,
        status="symbolic_only",
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=True,
        symbolic_start_seconds=float(string_index),
        symbolic_midi=midi,
        symbolic_import_confidence=1.0,
        alignment_confidence=0.9,
    )


def _chart(notes: list[ReconciledBassNote]) -> ReconciledBassChart:
    return ReconciledBassChart(
        source_sha256="a" * 64,
        track_index=4,
        onset_tolerance_seconds=0.15,
        verified_onset_tolerance_seconds=0.08,
        notes=notes,
    )


def test_infers_nonstandard_reviewed_tuning_from_symbolic_positions() -> None:
    chart = _chart([
        _note(string_index=0, fret=5, midi=31),  # Drop-D low string: 26 + 5
        _note(string_index=1, fret=2, midi=35),
        _note(string_index=2, fret=7, midi=45),
        _note(string_index=3, fret=3, midi=46),
    ])

    tuning = _infer_reconciled_bass_tuning(chart)

    assert tuning is not None
    assert tuning.open_midi == (26, 33, 38, 43)
    assert tuning.name == "Reviewed symbolic source"


def test_partial_uniform_offset_can_recover_eb_standard() -> None:
    chart = _chart([
        _note(string_index=0, fret=0, midi=27),
        _note(string_index=1, fret=5, midi=37),
    ])

    tuning = _infer_reconciled_bass_tuning(chart, E_STANDARD)

    assert tuning is not None
    assert tuning.open_midi == (27, 32, 37, 42)
    assert "-1 semitone offset" in tuning.name


def test_partial_evidence_without_fallback_is_not_guessed() -> None:
    chart = _chart([
        _note(string_index=0, fret=0, midi=27),
        _note(string_index=1, fret=5, midi=37),
    ])

    assert _infer_reconciled_bass_tuning(chart) is None


def test_partial_nonuniform_offsets_are_not_extrapolated() -> None:
    chart = _chart([
        _note(string_index=0, fret=0, midi=27),  # -1 from E standard
        _note(string_index=1, fret=0, midi=33),  # 0 from E standard
    ])

    assert _infer_reconciled_bass_tuning(chart, E_STANDARD) is None


def test_inconsistent_symbolic_tuning_evidence_is_refused() -> None:
    inconsistent = _chart([
        _note(string_index=0, fret=5, midi=31),
        _note(string_index=0, fret=4, midi=31),
        _note(string_index=1, fret=2, midi=35),
        _note(string_index=2, fret=7, midi=45),
        _note(string_index=3, fret=3, midi=46),
    ])

    assert _infer_reconciled_bass_tuning(inconsistent, E_STANDARD) is None


def test_ignores_audio_only_evidence_when_inferring_tuning() -> None:
    notes = [
        _note(string_index=0, fret=5, midi=31),
        _note(string_index=1, fret=2, midi=35),
        _note(string_index=2, fret=7, midi=45),
        _note(string_index=3, fret=3, midi=46),
        ReconciledBassNote(
            start_seconds=10.0,
            duration_seconds=0.25,
            midi=12,
            status="audio_only",
            trust_class=SourceTrustClass.audio_derived,
            review_required=True,
            audio_start_seconds=10.0,
            audio_midi=12,
            audio_confidence=0.8,
            alignment_confidence=0.8,
        ),
    ]

    tuning = _infer_reconciled_bass_tuning(_chart(notes))

    assert tuning is not None
    assert tuning.open_midi == (26, 33, 38, 43)
