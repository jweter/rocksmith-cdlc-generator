from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport, map_source_time
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.eof_beat_phase_project_alignment import refine_project_alignment_from_beat_phase
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceNoteEvent, SourceProvenance, SourceTrack
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _source_note(start: float) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=0.2,
        midi=40,
        string_index=0,
        fret=0,
        import_confidence=1.0,
    )


def _audio_note(start: float) -> NoteEvent:
    return NoteEvent(
        start=start,
        duration=0.2,
        midi=40,
        confidence=0.95,
        pitch_confidence=0.95,
        timing_confidence=0.95,
        review_required=False,
    )


def test_project_alignment_rebuilds_gp_timing_from_audio_beat_phase(tmp_path: Path) -> None:
    project = tmp_path / "song"
    analysis = project / "analysis"
    sources = project / "sources" / "imported"
    analysis.mkdir(parents=True)
    sources.mkdir(parents=True)

    source_path = sources / "fixture-bass.json"
    source_starts = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5]
    ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="fixture.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[0.5 * index for index in range(48)],
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Bass",
                instrument="bass",
                notes=[_source_note(start) for start in source_starts],
            )
        ],
    ).write_json(source_path)

    # Existing/incorrect baseline: the first score note at source 4.0s maps to 11.773s.
    baseline_offset = 7.773
    anchors = [
        AlignmentAnchor(
            source_time_seconds=value,
            audio_time_seconds=value + baseline_offset,
            source_beat_index=index * 8,
            audio_beat_index=index * 8,
            confidence=0.95,
        )
        for index, value in enumerate((0.0, 4.0, 8.0, 12.0, 16.0, 20.0))
    ]
    AlignmentReport(
        source_path=str(source_path),
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=2,
        audio_beat_start_index=0,
        global_offset_seconds=baseline_offset,
        anchor_stride_beats=8,
        matched_beats=48,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.95,
        anchors=anchors,
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=20.0,
                audio_start_seconds=baseline_offset,
                audio_end_seconds=20.0 + baseline_offset,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.95,
            )
        ],
    ).write_json(analysis / "alignment.json")

    # Symbolic source beat zero belongs to audio beat 6. Source first playable is symbolic
    # beat 8, which therefore lands at audio beat 14 == 7.13s.
    beat_times = [0.13 + 0.5 * index for index in range(64)]
    tempo_map = TempoMap(
        engine="fixture",
        beats=[
            BeatEvent(
                time=time,
                beat=(index % 4) + 1,
                measure=(index // 4) + 1,
                bpm=120.0,
                confidence=0.98,
                is_downbeat=index % 4 == 0,
            )
            for index, time in enumerate(beat_times)
        ],
    )
    write_tempo_map(tempo_map, analysis / "tempo_map.json")

    # Correct first phrase begins at 7.13s. A complete later repeat is present eight beats
    # later; the phase solver must not bind the score origin to that later occurrence.
    early = [7.13 + 0.5 * index for index in range(len(source_starts))]
    late = [11.13 + 0.5 * index for index in range(len(source_starts))]
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[*[_audio_note(value) for value in early], *[_audio_note(value) for value in late]],
        ),
        analysis / "bass_raw.json",
    )

    refine_project_alignment_from_beat_phase(project, source_path)

    refined = AlignmentReport.model_validate_json((analysis / "alignment.json").read_text(encoding="utf-8"))
    assert refined.audio_beat_start_index == 6
    assert refined.anchor_stride_beats == 1
    assert refined.anchors[0].audio_beat_index == 6
    assert refined.anchors[1].audio_beat_index == 7
    assert map_source_time(refined, 4.0) == pytest.approx(7.13, abs=0.001)
    assert map_source_time(refined, 4.25) == pytest.approx(7.38, abs=0.001)

    evidence = (analysis / "eof_first_sync_alignment.json").read_text(encoding="utf-8")
    assert "audio click lattice at beat index 6" in evidence
    assert "was not applied as a free-floating seconds offset" in evidence
