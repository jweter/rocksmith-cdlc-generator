"""Original synthetic audio, verified first-entrance clock, and two-engine scoring.

The source is freshly synthesized from a fixed score in temp folders. The
tests do NOT claim auto-cdlc has been executed or passed a real-song test.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import wave

import pytest

from rocksmith_cdlc_generator.auto_cdlc_truth import (
    KnownTruthError,
    generate_known_truth,
    verify_known_truth,
)
from rocksmith_cdlc_generator.auto_cdlc_truth_benchmark import run_known_truth_benchmark
from rocksmith_cdlc_generator.auto_cdlc_truth_cli import build_parser
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.midi_export import write_bass_midi
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _make_fixture(tmp_path: Path):
    folder = tmp_path / "fixture"
    audio, truth_path = generate_known_truth(folder)
    return folder, audio, json.loads(truth_path.read_text())


def _upstream_fixture(
    tmp_path: Path, truth: dict,
    *, shift: float = 0.0, octave: bool = False,
    omit_first: bool = False, beat_shift: float = 0.0,
    duration_shift: float = 0.0,
):
    folder = tmp_path / "fake-upstream"
    folder.mkdir()
    notes = truth["bass_notes"][1:] if omit_first else truth["bass_notes"]
    events = [
        NoteEvent(
            start=float(note["onset_seconds"]) + shift,
            duration=max(0.01, float(note["duration_seconds"]) + duration_shift),
            midi=int(note["midi"]) + (12 if octave and i % 3 == 0 else 0),
            confidence=1.0, timing_confidence=1.0, pitch_confidence=1.0,
        ) for i, note in enumerate(notes)
    ]
    transcription = BassTranscription(
        engine="synthetic-stand-in-NOT-auto-cdlc",
        source_path="original_synthetic.wav", sample_rate_hz=44100, notes=events
    )
    write_bass_midi(transcription, folder / "test.mid")

    # Upstream writes a four-beat COUNT before song beats; SVL (unlike MIDI)
    # has an additional recorded silence shift. Here silence=1.25 seconds.
    padding = 1.25
    beats = truth["beats_seconds"]
    before = [beats[0] - delta for delta in (2.0, 1.5, 1.0, 0.5)]
    timestamps = before + beats
    labels = [1, 2, 3, 4] + [i % 4 + 1 for i in range(len(beats))]
    rows = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!DOCTYPE sonic-visualiser>",
        "<sv><data>",
        '<model id="1" name="Beats" sampleRate="44100" start="0" end="1500000" type="sparse" dimensions="1" resolution="1" notifyOnAdd="true" dataset="0" />',
        '<dataset id="0" dimensions="1">',
    ]
    rows.extend(
        f'<point frame="{round((t + padding + beat_shift) * 44100)}" label="{label}" />'
        for t, label in zip(timestamps, labels)
    )
    rows.extend(["</dataset>", "</data></sv>"])
    (folder / "test.svl").write_text("\n".join(rows), encoding="utf-8")
    (folder / "diagnostico.json").write_text(
        json.dumps({"version": "0.4.2", "resultado": {"silencio_inicial_s": padding}}),
        encoding="utf-8",
    )
    return folder


def _local_fixture(tmp_path: Path, truth: dict, audio: Path, *, shift: float = 0.0):
    folder = tmp_path / "local-project"
    (folder / "source").mkdir(parents=True)
    (folder / "analysis").mkdir()
    source = folder / "source" / audio.name
    shutil.copyfile(audio, source)
    ProjectManifest(
        project_name="Synthetic Original Music",
        title="Synthetic Original Music",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path=str(source),
        source_project_path="source/" + audio.name,
        source_sha256=sha256_file(source),
        source_metadata=AudioMetadata(
            duration_seconds=truth["duration_seconds"],
            sample_rate_hz=44100,
            channels=1,
        ),
    ).save(folder)
    notes = [
        NoteEvent(
            start=float(n["onset_seconds"]) + shift,
            duration=float(n["duration_seconds"]),
            midi=int(n["midi"]),
            confidence=1.0, pitch_confidence=1.0, timing_confidence=1.0,
        )
        for n in truth["bass_notes"]
    ]
    write_transcription(
        BassTranscription(
            engine="synthetic-stand-in-NOT-real-generator",
            source_path=str(source),
            sample_rate_hz=44100,
            notes=notes,
        ), folder / "analysis/bass_raw.json"
    )
    write_tempo_map(
        TempoMap(engine="synthetic-stand-in-NOT-real-generator", beats=[
            BeatEvent(
                time=float(t), beat=i % 4 + 1, measure=i // 4 + 1,
                bpm=120, confidence=1.0, is_downbeat=(i % 4 == 0),
            ) for i, t in enumerate(truth["beats_seconds"])
        ]), folder / "analysis/tempo_map.json"
    )
    return folder


def _run(folder: Path, tmp_path: Path, *, upstream: Path | None = None, project: Path | None = None):
    return run_known_truth_benchmark(
        folder, upstream_dir=upstream, local_project=project,
        out_path=tmp_path / "synthetic_aggregate.json",
    )


def test_created_audio_is_real_pcm_with_sample_exact_first_beat(tmp_path):
    folder, audio, truth = _make_fixture(tmp_path)
    with wave.open(str(audio), "rb") as data:
        assert data.getframerate() == 44100
        assert data.getnchannels() == 1
        assert data.getsampwidth() == 2
        assert data.getnframes() == round(truth["duration_seconds"] * 44100)
    assert truth["beats_seconds"][0] == pytest.approx(7.13)
    assert truth["bass_notes"][0]["onset_seconds"] == pytest.approx(7.13)
    assert len(truth["beats_seconds"]) == 40
    assert len(truth["bass_notes"]) == 36
    assert sha256_file(audio) == truth["source_audio_sha256"]
    assert verify_known_truth(folder)[1] == truth


def test_generate_is_idempotent_and_fails_closed_on_mutation(tmp_path):
    folder, audio, truth = _make_fixture(tmp_path)
    original = audio.read_bytes()
    assert generate_known_truth(folder)[0].read_bytes() == original
    audio.write_bytes(b"tampered")
    with pytest.raises(KnownTruthError, match="unrelated synthetic audio"):
        generate_known_truth(folder)
    with pytest.raises(KnownTruthError, match="waveform"):
        verify_known_truth(folder)


def test_truth_json_forgery_is_rejected_without_report(tmp_path):
    folder, audio, truth = _make_fixture(tmp_path)
    metadata = folder / "fixture.json"
    truth["bass_notes"][0]["onset_seconds"] += 4
    metadata.write_text(json.dumps(truth), encoding="utf-8")
    with pytest.raises(KnownTruthError, match="differs"):
        verify_known_truth(folder)
    assert not (tmp_path / "synthetic_aggregate.json").exists()


def test_perfect_simulated_upstream_comparison_on_original_clock(tmp_path):
    folder, _audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth)
    report = _run(folder, tmp_path, upstream=upstream)
    measured = report["engine_results"]["auto_cdlc"]
    assert measured["fixture_verdict"] == "PASS"
    assert measured["note_f1"] == 1.0
    assert measured["first_bass_onset_phase_seconds"] == pytest.approx(0, abs=0.0011)
    assert measured["first_beat_phase_seconds"] == pytest.approx(0, abs=1 / 44100)
    assert measured["downbeat_f1"] == 1.0
    assert report["scope"] == "SYNTHETIC_FIXTURE_ONLY"
    assert report["rocksmith_gameplay_proven"] is False
    assert report["producer_input_output_binding"] == "UNPROVEN"


def test_identical_two_bar_riff_shift_cannot_pass(tmp_path):
    folder, _audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth, shift=4.0)
    result = _run(folder, tmp_path, upstream=upstream)
    scored = result["engine_results"]["auto_cdlc"]
    assert scored["fixture_verdict"] == "FAIL"
    assert "FIRST_BASS_ONSET_OUT_OF_PHASE" in scored["failure_reasons"]
    assert scored["first_bass_onset_phase_seconds"] == pytest.approx(4.0, abs=0.002)


def test_octave_class_equivalence_must_not_pass(tmp_path):
    folder, _audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth, octave=True)
    result = _run(folder, tmp_path, upstream=upstream)
    scored = result["engine_results"]["auto_cdlc"]
    assert scored["fixture_verdict"] == "FAIL"
    assert scored["note_f1"] < 0.90
    assert "BASS_NOTE_F1_BELOW_0_90" in scored["failure_reasons"]


def test_missing_first_note_is_detected_even_if_recall_is_high(tmp_path):
    folder, _audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth, omit_first=True)
    result = _run(folder, tmp_path, upstream=upstream)
    scored = result["engine_results"]["auto_cdlc"]
    assert scored["fixture_verdict"] == "FAIL"
    assert "FIRST_BASS_ONSET_OUT_OF_PHASE" in scored["failure_reasons"]


def test_wrong_note_duration_is_detected(tmp_path):
    folder, _audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth, duration_shift=0.16)
    scored = _run(folder, tmp_path, upstream=upstream)["engine_results"]["auto_cdlc"]
    assert scored["fixture_verdict"] == "FAIL"
    assert "BASS_DURATION_ERROR" in scored["failure_reasons"]


def test_beat_and_downbeat_phase_errors_are_separately_detected(tmp_path):
    folder, _audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth, beat_shift=0.5)
    scored = _run(folder, tmp_path, upstream=upstream)["engine_results"]["auto_cdlc"]
    assert scored["fixture_verdict"] == "FAIL"
    assert "FIRST_BEAT_OUT_OF_PHASE" in scored["failure_reasons"]


def test_local_project_compared_with_exact_verified_original_source(tmp_path):
    folder, audio, truth = _make_fixture(tmp_path)
    local = _local_fixture(tmp_path, truth, audio)
    report = _run(folder, tmp_path, project=local)
    assert report["engine_results"]["our_generator"]["fixture_verdict"] == "PASS"
    assert report["engine_results"]["our_generator"]["artifact_source_binding"] == "UNPROVEN"
    assert report["comparison_verdict"] == "PASS"


def test_local_project_four_second_shift_fails_and_cannot_auto_promote(tmp_path):
    folder, audio, truth = _make_fixture(tmp_path)
    local = _local_fixture(tmp_path, truth, audio, shift=4.0)
    report = _run(folder, tmp_path, project=local)
    assert report["engine_results"]["our_generator"]["fixture_verdict"] == "FAIL"
    assert report["real_song_accuracy_proven"] is False


def test_both_engine_results_are_separate_and_privacy_sanitized(tmp_path):
    folder, audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth)
    local = _local_fixture(tmp_path, truth, audio)
    report = _run(folder, tmp_path, project=local, upstream=upstream)
    assert set(report["engine_results"]) == {"our_generator", "auto_cdlc"}
    assert report["comparison_verdict"] == "PASS"
    content = (tmp_path / "synthetic_aggregate.json").read_text()
    assert json.loads(content) == report
    assert str(tmp_path) not in content
    assert "bass_notes" not in content
    assert "original_synthetic.wav" not in content
    assert "source/original_synthetic.wav" not in content


def test_prevent_overwriting_any_fixture_or_engine_input(tmp_path):
    folder, audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth)
    local = _local_fixture(tmp_path, truth, audio)
    protected = [audio, folder / "fixture.json", upstream / "test.mid", local / "analysis/bass_raw.json"]
    for item in protected:
        original = item.read_bytes()
        with pytest.raises(KnownTruthError, match="Unsafe|Report inside|Report must|overwrit"):
            run_known_truth_benchmark(folder, upstream_dir=upstream, local_project=local, out_path=item)
        assert item.read_bytes() == original


def test_existing_non_report_is_not_replaced_and_own_report_refresh_is_safe(tmp_path):
    folder, _audio, truth = _make_fixture(tmp_path)
    upstream = _upstream_fixture(tmp_path, truth)
    report_file = tmp_path / "synthetic_aggregate.json"
    report_file.write_text("private notes", encoding="utf-8")
    with pytest.raises(KnownTruthError, match="unrelated"):
        _run(folder, tmp_path, upstream=upstream)
    assert report_file.read_text() == "private notes"
    report_file.unlink()
    first = _run(folder, tmp_path, upstream=upstream)
    second = _run(folder, tmp_path, upstream=upstream)
    assert first == second
    assert not list(tmp_path.glob(".cdlc-synthetic-truth-*"))


def test_no_prediction_artifacts_is_not_an_accepted_benchmark(tmp_path):
    folder, _audio, _truth = _make_fixture(tmp_path)
    with pytest.raises(KnownTruthError, match="at least one"):
        _run(folder, tmp_path)


def test_cli_requires_bounded_paths(tmp_path):
    args = build_parser().parse_args(["generate", "--out-dir", str(tmp_path)])
    assert args.command == "generate"
    args = build_parser().parse_args([
        "evaluate", "--fixture-dir", str(tmp_path / "fixture"),
        "--upstream-dir", str(tmp_path / "upstream"), "--out", str(tmp_path / "report.json"),
    ])
    assert args.command == "evaluate"
    assert args.upstream_dir == tmp_path / "upstream"
