"""Synthetic contract tests for untrusted fesaje/auto-cdlc MIDI + SVL evidence.

No real songs, third-party models, original proprietary files or upstream
executables are needed. The upstream MIDI is on the original audio clock;
the SVL contains a padded four-beat count-in and a separate audio delay.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.auto_cdlc_oracle import (
    AutoCdlcOracleError,
    compare_auto_cdlc_export,
    read_upstream_midi,
    read_upstream_svl,
)
from rocksmith_cdlc_generator.auto_cdlc_oracle_cli import build_parser
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.midi_export import write_bass_midi
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription

PITCHES = (40, 43, 45, 47, 48, 50, 52, 55)
BEATS = [round(7.13 + 0.5 * i, 3) for i in range(32)]
PADDING_SECONDS = 1.25
NAME = "PersonalSong_DO_NOT_REPORT"


def _events(*, shift: float = 0, octave: bool = False) -> list[NoteEvent]:
    return [
        NoteEvent(
            start=t + shift,
            duration=0.28,
            midi=PITCHES[i % len(PITCHES)] + (12 if octave and i % 3 == 0 else 0),
            confidence=0.95,
            timing_confidence=0.95,
            pitch_confidence=0.95,
        )
        for i, t in enumerate(BEATS)
    ]


def _fixture(tmp_path: Path, *, ours_shift: float = 0, ours_octave: bool = False):
    project = tmp_path / NAME
    upstream = tmp_path / "upstream-private-output"
    (project / "source").mkdir(parents=True)
    (project / "analysis").mkdir()
    upstream.mkdir()

    source = project / "source" / "original.mp3"
    source.write_bytes(b"synthetic-audio-placeholder-for-clock-test")
    ProjectManifest(
        project_name=NAME,
        title=NAME,
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path=str(source),
        source_project_path="source/original.mp3",
        source_sha256=sha256_file(source),
        source_metadata=AudioMetadata(duration_seconds=60, sample_rate_hz=44100, channels=2),
    ).save(project)

    write_tempo_map(TempoMap(
        engine="synthetic",
        beats=[
            BeatEvent(
                time=t, beat=i % 4 + 1, measure=i // 4 + 1,
                bpm=120.0, confidence=1.0, is_downbeat=(i % 4 == 0),
            )
            for i, t in enumerate(BEATS)
        ],
    ), project / "analysis" / "tempo_map.json")
    local = BassTranscription(
        engine="synthetic-generator",
        source_path=str(source),
        sample_rate_hz=44100,
        notes=_events(shift=ours_shift, octave=ours_octave),
    )
    write_transcription(local, project / "analysis" / "bass_raw.json")

    # Reconstruct exactly the tested upstream source contract:
    # first 4 points = artificial COUNT, rest = padded original beat grid.
    points = [BEATS[0] - 0.5 * n for n in (4, 3, 2, 1)] + BEATS
    labels = [1, 2, 3, 4] + [i % 4 + 1 for i in range(len(BEATS))]
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!DOCTYPE sonic-visualiser>",
        "<sv>", "<data>",
        '<model id="1" name="Beats" sampleRate="44100" start="0" end="12345" type="sparse" dimensions="1" resolution="1" notifyOnAdd="true" dataset="0" />',
        '<dataset id="0" dimensions="1">',
    ]
    xml.extend(
        f'<point frame="{round((t + PADDING_SECONDS) * 44100)}" label="{label}" />'
        for t, label in zip(points, labels)
    )
    xml.extend(["</dataset>", "</data>", "</sv>"])
    (upstream / "song.svl").write_text("\n".join(xml), encoding="utf-8")
    upstream_bass = BassTranscription(
        engine="synthetic-upstream", source_path=str(source),
        sample_rate_hz=44100, notes=_events(),
    )
    write_bass_midi(upstream_bass, upstream / "song.mid")
    (upstream / "diagnostico.json").write_text(
        json.dumps({
            "version": "0.4.2",
            "resultado": {"silencio_inicial_s": PADDING_SECONDS},
            "artista": NAME,
            "tablatura": {"private_notes": [40, 43, 45]},
        }),
        encoding="utf-8",
    )
    return project, upstream, source


def _run(project: Path, upstream: Path, source: Path, tmp_path: Path):
    return compare_auto_cdlc_export(
        project, upstream, upstream_audio=source, out_path=tmp_path / "aggregate.json",
    )


def test_upstream_svl_padded_clock_is_unpadded_without_shifted_midi(tmp_path):
    project, upstream, source = _fixture(tmp_path)
    beats, downs = read_upstream_svl(
        upstream / "song.svl", padding_seconds=PADDING_SECONDS,
    )
    assert beats[0] == pytest.approx(7.13, abs=1 / 44100)
    assert downs[0] == pytest.approx(7.13, abs=1 / 44100)
    midi = read_upstream_midi(upstream / "song.mid")
    assert midi[0].onset_seconds == pytest.approx(7.13, abs=0.001)
    assert midi[0].duration_seconds == pytest.approx(0.28, abs=0.001)
    report = _run(project, upstream, source, tmp_path)
    assert report["beat_grid"]["f1"] == 1.0
    assert report["downbeat_grid"]["f1"] == 1.0
    assert report["bass_notes"]["first_event_phase_seconds"] == pytest.approx(0.0, abs=0.002)
    assert report["alerts"] == []
    assert report["verdict"] == "REVIEW_REQUIRED"
    assert report["reference_authority"] == "NONE"


def test_two_bar_shift_is_visible_even_with_periodic_repeated_notes(tmp_path):
    project, upstream, source = _fixture(tmp_path, ours_shift=4.0)
    report = _run(project, upstream, source, tmp_path)
    assert "FIRST_BASS_ONSET_CLOCK_DISAGREEMENT" in report["alerts"]
    assert report["bass_notes"]["first_event_phase_seconds"] == pytest.approx(4.0, abs=0.002)
    assert report["beat_grid"]["f1"] == 1.0
    assert report["verdict"] == "REVIEW_REQUIRED"


def test_octave_error_is_detected_even_when_pitch_class_is_equal(tmp_path):
    project, upstream, source = _fixture(tmp_path, ours_octave=True)
    report = _run(project, upstream, source, tmp_path)
    assert "BASS_MIDI_PITCH_OR_OCTAVE_DISAGREEMENT" in report["alerts"]
    assert report["bass_notes"]["counts"]["wrong_pitch"] > 0
    assert report["bass_notes"]["pitch_agreement"] < 0.95


def test_mismatched_original_audio_is_rejected_before_any_report(tmp_path):
    project, upstream, source = _fixture(tmp_path)
    unrelated = tmp_path / "wrong-source.mp3"
    unrelated.write_bytes(b"another-mix")
    with pytest.raises(AutoCdlcOracleError, match="must match immutable project source"):
        _run(project, upstream, unrelated, tmp_path)
    assert not (tmp_path / "aggregate.json").exists()


def test_unverified_upstream_output_is_never_promoted(tmp_path):
    project, upstream, source = _fixture(tmp_path)
    report = _run(project, upstream, source, tmp_path)
    assert report["bass_notes"]["trust_tier"] == "C"
    assert report["bass_notes"]["authoritative"] is False
    assert report["bass_notes"]["verdict"] == "REVIEW_REQUIRED"
    assert "upstream_export_identity_unproven" in report["source_binding"]


def test_sanitized_report_has_no_private_note_arrays_or_identifiers(tmp_path):
    project, upstream, source = _fixture(tmp_path)
    report = _run(project, upstream, source, tmp_path)
    raw = (tmp_path / "aggregate.json").read_text()
    assert json.loads(raw) == report
    assert NAME not in raw
    assert str(project) not in raw
    assert str(upstream) not in raw
    assert str(source) not in raw
    assert "private_notes" not in raw
    assert len(report["input_sha256"]["upstream_midi"]) == 64
    assert "input_sha256" in report and "build_identity" in report


def test_svl_without_count_in_is_refused_rather_than_guess_offset(tmp_path):
    _project, upstream, _source = _fixture(tmp_path)
    p = upstream / "song.svl"
    p.write_text(p.read_text().replace('label="2"', 'label="3"', 1), encoding="utf-8")
    with pytest.raises(AutoCdlcOracleError, match="COUNT pattern"):
        read_upstream_svl(p, padding_seconds=PADDING_SECONDS)


def test_svl_external_entity_is_refused(tmp_path):
    _project, upstream, _source = _fixture(tmp_path)
    p = upstream / "song.svl"
    p.write_text(p.read_text().replace("<!DOCTYPE sonic-visualiser>", '<!DOCTYPE sonic-visualiser [<!ENTITY x SYSTEM "file:///secret">]>'), encoding="utf-8")
    with pytest.raises(AutoCdlcOracleError, match="DOCTYPE|entity|declaration"):
        read_upstream_svl(p, padding_seconds=PADDING_SECONDS)


def test_ambiguous_upstream_midi_is_refused(tmp_path):
    _project, upstream, _source = _fixture(tmp_path)
    (upstream / "second.mid").write_bytes((upstream / "song.mid").read_bytes())
    with pytest.raises(AutoCdlcOracleError, match="exactly one \\.mid"):
        _run(_project, upstream, _source, tmp_path)


def test_diagnostic_missing_silence_is_refused(tmp_path):
    project, upstream, source = _fixture(tmp_path)
    (upstream / "diagnostico.json").write_text('{"resultado":{}}', encoding="utf-8")
    with pytest.raises(AutoCdlcOracleError, match="silencio_inicial_s"):
        _run(project, upstream, source, tmp_path)


def test_cli_requires_both_source_fingerprint_and_private_output(tmp_path):
    args = build_parser().parse_args([
        "--project", str(tmp_path / "project"),
        "--upstream-dir", str(tmp_path / "output"),
        "--upstream-audio", str(tmp_path / "original.mp3"),
        "--out", str(tmp_path / "report.json"),
    ])
    assert args.project.name == "project"
    assert args.upstream_audio.name == "original.mp3"
    assert args.out.name == "report.json"
