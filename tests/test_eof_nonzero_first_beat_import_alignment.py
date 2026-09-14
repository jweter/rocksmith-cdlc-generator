from pathlib import Path

import pytest

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.eof_beat_phase_alignment import (
    map_symbolic_beat_to_audio_time,
    solve_beat_phase,
)
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.guitar_authoring import GuitarAuthoringChart, GuitarAuthoringNote
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.rocksmith_xml import build_rocksmith_bass_xml, build_rocksmith_guitar_xml
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _manifest(tmp_path: Path) -> ProjectManifest:
    return ProjectManifest(
        project_name="eof-nonzero-first-beat-import",
        artist="Synthetic",
        title="Nonzero First Beat Import Alignment",
        source_original_path="source.wav",
        source_project_path="source/source.wav",
        source_sha256="0" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=8.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )


def _nonzero_origin_tempo_map() -> TempoMap:
    # The recording's first authoritative beat does not occur at 0 s (a leading
    # count-in/intro). This is canonical timing state, not intro silence to discard.
    times = [0.75, 1.25, 1.75, 2.25, 2.75, 3.25]
    return TempoMap(
        engine="eof-nonzero-first-beat-import-fixture",
        time_signature_numerator=4,
        time_signature_denominator=4,
        beats=[
            BeatEvent(time=time, beat=(index % 4) + 1, measure=(index // 4) + 1, bpm=120.0, confidence=1.0, is_downbeat=index % 4 == 0)
            for index, time in enumerate(times)
        ],
    )


def _bass_mapping(note_time: float) -> BassMapping:
    return BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=note_time,
                duration=0.25,
                midi=40,
                string=0,
                fret=0,
                source_confidence=1.0,
                mapping_confidence=1.0,
            )
        ],
    )


def _guitar_chart(arrangement: str, note_time: float) -> GuitarAuthoringChart:
    return GuitarAuthoringChart(
        arrangement=arrangement,
        source_sha256="a" * 64,
        alignment_confidence=1.0,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[
            GuitarAuthoringNote(
                start_seconds=note_time,
                duration_seconds=0.25,
                midi=64,
                string_index=5,
                fret=0,
                techniques=[],
                trust_class=SourceTrustClass.symbolic_verified,
                review_required=False,
            )
        ],
        chords=[],
    )


def test_solved_import_phase_preserves_nonzero_origin_through_shared_export(tmp_path: Path) -> None:
    """EOF import/alignment-boundary parity fixture for #414/#455.

    Completes the deterministic fixture recorded as remaining in
    docs/eof-audits/chart-delay-nonzero-first-beat-2026-09-13.md after the export-boundary
    half was covered by test_eof_nonzero_first_beat_export.py. This proves the whole chain --
    phase solving, symbolic-to-audio alignment, and the shared Bass/Lead/Rhythm export
    boundary -- preserves a non-zero recording origin exactly once, with no song-specific
    offset introduced at any stage.
    """

    tempo = _nonzero_origin_tempo_map()

    # A symbolic score/import layer only knows beat-relative coordinates starting at its own
    # beat zero. The audio recording's matching onsets sit on the tempo map's non-zero-origin
    # beats above (0.75 s, 1.25 s, 1.75 s, 2.25 s), never on absolute symbolic-time zero.
    symbolic_onset_positions = [0.0, 1.0, 2.0, 3.0]
    audio_onsets_seconds = [0.75, 1.25, 1.75, 2.25]

    solution = solve_beat_phase(
        tempo,
        symbolic_onset_positions=symbolic_onset_positions,
        audio_onsets_seconds=audio_onsets_seconds,
    )

    # The correct phase binds symbolic beat zero to the recording's actual (non-zero) first
    # beat rather than silently assuming beat zero begins at recording time zero.
    assert solution.audio_beat_start_index == 0
    assert solution.matched_onsets == len(symbolic_onset_positions)
    assert solution.mean_abs_error_seconds == pytest.approx(0.0)

    mapped_beat_zero = map_symbolic_beat_to_audio_time(
        tempo,
        audio_beat_start_index=solution.audio_beat_start_index,
        symbolic_beat_position=0.0,
    )
    # Symbolic beat zero must land on the recording's non-zero first beat, not on 0 s.
    assert mapped_beat_zero == pytest.approx(0.75)

    # An imported note between beats (not itself an onset used to solve phase) must be
    # interpolated from the authoritative audio anchors, not derived from a stored offset.
    mapped_note_time = map_symbolic_beat_to_audio_time(
        tempo,
        audio_beat_start_index=solution.audio_beat_start_index,
        symbolic_beat_position=1.5,
    )
    assert mapped_note_time == pytest.approx(1.5)

    manifest = _manifest(tmp_path)
    roots = [
        build_rocksmith_bass_xml(manifest, tempo, _bass_mapping(mapped_note_time)),
        build_rocksmith_guitar_xml(manifest, tempo, _guitar_chart("lead", mapped_note_time)),
        build_rocksmith_guitar_xml(manifest, tempo, _guitar_chart("rhythm", mapped_note_time)),
    ]

    for root in roots:
        assert float(root.findtext("startBeat")) == pytest.approx(0.75)
        first_ebeat = root.find("ebeats/ebeat")
        assert first_ebeat is not None
        assert float(first_ebeat.attrib["time"]) == pytest.approx(0.75)

        notes = root.findall("levels/level/notes/note")
        assert len(notes) == 1
        # The solved import-alignment time survives to export exactly once: neither the
        # non-zero first-beat origin nor the phase-solving offset is re-applied on top of it.
        assert float(notes[0].attrib["time"]) == pytest.approx(mapped_note_time)
