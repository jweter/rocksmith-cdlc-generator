from pathlib import Path

import pytest

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.guitar_authoring import GuitarAuthoringChart, GuitarAuthoringNote
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.rocksmith_xml import build_rocksmith_bass_xml, build_rocksmith_guitar_xml
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _manifest(tmp_path: Path) -> ProjectManifest:
    return ProjectManifest(
        project_name="eof-nonzero-first-beat",
        artist="Synthetic",
        title="Nonzero First Beat",
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


def _shared_tempo() -> TempoMap:
    return TempoMap(
        engine="eof-nonzero-first-beat-fixture",
        time_signature_numerator=4,
        time_signature_denominator=4,
        beats=[
            BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=1.0, is_downbeat=True),
            BeatEvent(time=1.0, beat=2, measure=1, bpm=120.0, confidence=1.0),
            BeatEvent(time=1.5, beat=3, measure=1, bpm=120.0, confidence=1.0),
            BeatEvent(time=2.0, beat=4, measure=1, bpm=120.0, confidence=1.0),
            BeatEvent(time=2.5, beat=1, measure=2, bpm=120.0, confidence=1.0, is_downbeat=True),
        ],
    )


def _bass_mapping() -> BassMapping:
    return BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=1.0,
                duration=0.25,
                midi=40,
                string=0,
                fret=0,
                source_confidence=1.0,
                mapping_confidence=1.0,
            )
        ],
    )


def _guitar_chart(arrangement: str) -> GuitarAuthoringChart:
    return GuitarAuthoringChart(
        arrangement=arrangement,
        source_sha256="a" * 64,
        alignment_confidence=1.0,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[
            GuitarAuthoringNote(
                start_seconds=1.0,
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


def _assert_nonzero_origin_preserved(root) -> None:
    assert float(root.findtext("startBeat")) == pytest.approx(0.5)
    first_ebeat = root.find("ebeats/ebeat")
    assert first_ebeat is not None
    assert float(first_ebeat.attrib["time"]) == pytest.approx(0.5)
    note = root.find("levels/level/notes/note")
    assert note is not None
    assert float(note.attrib["time"]) == pytest.approx(1.0)


def test_shared_nonzero_first_beat_is_not_double_applied_across_arrangements(tmp_path: Path) -> None:
    """EOF parity fixture for #414/#455.

    A non-zero first authoritative beat is canonical timing state. Bass, Lead, and Rhythm all
    consume the same TempoMap and must retain the event phase exactly once at the XML boundary.
    See docs/eof-audits/chart-delay-nonzero-first-beat-2026-09-13.md.
    """

    manifest = _manifest(tmp_path)
    tempo = _shared_tempo()

    roots = [
        build_rocksmith_bass_xml(manifest, tempo, _bass_mapping()),
        build_rocksmith_guitar_xml(manifest, tempo, _guitar_chart("lead")),
        build_rocksmith_guitar_xml(manifest, tempo, _guitar_chart("rhythm")),
    ]

    for root in roots:
        _assert_nonzero_origin_preserved(root)
