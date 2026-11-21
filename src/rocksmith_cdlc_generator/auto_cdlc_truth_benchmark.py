"""Absolute-clock synthetic musical truth benchmark for our Bass and auto-cdlc.

Only verified reproducible original audio is authoritative here. The result
grades this *synthetic fixture*, not musical playability or real-song accuracy.
Upstream and local result artifacts still need producer-side provenance.
"""
from __future__ import annotations

from dataclasses import asdict
import json
from math import isfinite
import os
from pathlib import Path
import tempfile

from .auto_cdlc_oracle import (
    _beat_agreement,
    _diagnostic,
    _one_export,
    read_upstream_midi,
    read_upstream_svl,
)
from .auto_cdlc_truth import KnownTruthError, PROFILE, verify_known_truth
from .beats import read_tempo_map
from .benchmark import BenchmarkChart, BenchmarkNote, evaluate_chart
from .build_identity import current_build_identity
from .corpus_differential import DiffNote, compare_arrangements
from .corpus_differential_harness import refuse_output_inside_repository_checkout
from .hashing import sha256_file
from .models import ProjectManifest
from .transcription import read_transcription

_KIND = "synthetic_known_truth_comparison_v1"
_MAX_REPORT_BYTES = 1024 * 1024


def _grade(
    truth: dict[str, object],
    *,
    note_events: list[DiffNote],
    beats: list[float],
    downbeats: list[float],
) -> dict[str, object]:
    """Score against absolute reference timestamps, with no optimized shift."""
    source_notes = [
        DiffNote(
            onset_seconds=float(n["onset_seconds"]),
            duration_seconds=float(n["duration_seconds"]),
            midi=int(n["midi"]),
        )
        for n in truth["bass_notes"]
    ]
    duration = float(truth["duration_seconds"])
    def chart(notes: list[DiffNote]) -> BenchmarkChart:
        return BenchmarkChart(
            case_id=PROFILE,
            arrangement="bass",
            audio_duration_seconds=duration,
            notes=[
                BenchmarkNote(
                    start_seconds=n.onset_seconds,
                    duration_seconds=n.duration_seconds,
                    midi=n.midi,
                )
                for n in notes
            ],
        )
    metrics = evaluate_chart(chart(source_notes), chart(note_events), onset_tolerance_seconds=0.12)
    differential = compare_arrangements(source_notes, note_events, trust_tier="B")
    expected_beats = [float(x) for x in truth["beats_seconds"]]
    expected_downbeats = [float(x) for x in truth["downbeats_seconds"]]
    beat_score = _beat_agreement(expected_beats, beats, tolerance=0.07)
    downbeat_score = _beat_agreement(expected_downbeats, downbeats, tolerance=0.07)
    first_note_phase = (
        min(n.onset_seconds for n in note_events) - source_notes[0].onset_seconds
        if note_events else None
    )
    first_beat_phase = beats[0] - expected_beats[0] if beats else None
    first_downbeat_phase = downbeats[0] - expected_downbeats[0] if downbeats else None

    reasons: list[str] = []
    if metrics.note_f1 < 0.90:
        reasons.append("BASS_NOTE_F1_BELOW_0_90")
    if first_note_phase is None or abs(first_note_phase) > 0.08:
        reasons.append("FIRST_BASS_ONSET_OUT_OF_PHASE")
    if metrics.onset_mae_seconds is None or metrics.onset_mae_seconds > 0.06:
        reasons.append("BASS_ABSOLUTE_ONSET_ERROR")
    if metrics.duration_mae_seconds is None or metrics.duration_mae_seconds > 0.08:
        reasons.append("BASS_DURATION_ERROR")
    if differential.onset_drift_seconds_per_minute is not None and abs(differential.onset_drift_seconds_per_minute) > 0.04:
        reasons.append("BASS_ONSET_DRIFT")
    if beat_score["f1"] is None or beat_score["f1"] < 0.95:
        reasons.append("BEAT_F1_BELOW_0_95")
    if first_beat_phase is None or abs(first_beat_phase) > 0.08:
        reasons.append("FIRST_BEAT_OUT_OF_PHASE")
    if downbeat_score["f1"] is None or downbeat_score["f1"] < 0.90:
        reasons.append("DOWNBEAT_F1_BELOW_0_90")
    if first_downbeat_phase is None or abs(first_downbeat_phase) > 0.08:
        reasons.append("FIRST_DOWNBEAT_OUT_OF_PHASE")
    return {
        "fixture_verdict": "FAIL" if reasons else "PASS",
        "failure_reasons": reasons,
        "reference_notes": metrics.reference_note_count,
        "predicted_notes": metrics.predicted_note_count,
        "matched_notes": metrics.matched_note_count,
        "note_f1": round(metrics.note_f1, 5),
        "false_positive_notes": metrics.false_positive_count,
        "false_negative_notes": metrics.false_negative_count,
        "first_bass_onset_phase_seconds": round(first_note_phase, 6) if first_note_phase is not None else None,
        "onset_mae_seconds": round(metrics.onset_mae_seconds, 6) if metrics.onset_mae_seconds is not None else None,
        "duration_mae_seconds": round(metrics.duration_mae_seconds, 6) if metrics.duration_mae_seconds is not None else None,
        "onset_drift_seconds_per_minute": differential.onset_drift_seconds_per_minute,
        "beat_f1": beat_score["f1"],
        "downbeat_f1": downbeat_score["f1"],
        "first_beat_phase_seconds": round(first_beat_phase, 6) if first_beat_phase is not None else None,
        "first_downbeat_phase_seconds": round(first_downbeat_phase, 6) if first_downbeat_phase is not None else None,
    }


def _write_report(
    out_path: Path, *, fixture: Path, upstream: Path | None, local_project: Path | None,
    report: dict[str, object]
) -> Path:
    out_path = out_path.expanduser().resolve()
    refuse_output_inside_repository_checkout(out_path)
    if out_path.suffix.lower() != ".json":
        raise KnownTruthError("Synthetic benchmark report must use a .json filename")
    if out_path.is_relative_to(fixture) and not out_path.is_relative_to(fixture / "reports"):
        raise KnownTruthError("Report inside fixture must be under reports/")
    if upstream is not None and out_path.is_relative_to(upstream):
        raise KnownTruthError("Report must not overwrite upstream outputs")
    if local_project is not None and out_path.is_relative_to(local_project) and not out_path.is_relative_to(local_project / "review"):
        raise KnownTruthError("Report inside a local project must be under review/")
    if out_path.exists():
        if not out_path.is_file() or out_path.stat().st_size > _MAX_REPORT_BYTES:
            raise KnownTruthError("Refusing to overwrite unrelated content")
        try:
            old = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise KnownTruthError("Refusing to overwrite unrelated content") from exc
        if not isinstance(old, dict) or old.get("kind") != _KIND or old.get("profile") != PROFILE:
            raise KnownTruthError("Refusing to overwrite unrelated content")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=out_path.parent,
            prefix=".cdlc-synthetic-truth-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, out_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return out_path


def run_known_truth_benchmark(
    fixture_dir: Path,
    *,
    upstream_dir: Path | None = None,
    local_project: Path | None = None,
    out_path: Path,
) -> dict[str, object]:
    """Compare 1-2 external artifacts with independently regenerated truth.

    Both prediction directories are optional independently, but at least one
    must be supplied. No model binaries, network calls or game files are used.
    """
    if upstream_dir is None and local_project is None:
        raise KnownTruthError("Pass at least one of upstream_dir and local_project")
    fixture = fixture_dir.expanduser().resolve()
    upstream = upstream_dir.expanduser().resolve() if upstream_dir else None
    project = local_project.expanduser().resolve() if local_project else None
    out_path = out_path.expanduser().resolve()
    refuse_output_inside_repository_checkout(out_path)
    # Reject destinations BEFORE reading any private upstream/local artifacts.
    if out_path.suffix.lower() != ".json" or (
        out_path.is_relative_to(fixture) and not out_path.is_relative_to(fixture / "reports")
    ) or (upstream is not None and out_path.is_relative_to(upstream)) or (
        project is not None and out_path.is_relative_to(project) and not out_path.is_relative_to(project / "review")
    ):
        raise KnownTruthError("Unsafe synthetic benchmark report destination")
    wav_path, truth = verify_known_truth(fixture)
    input_hashes: dict[str, str] = {
        "synthetic_audio": sha256_file(wav_path),
        "fixture_truth": sha256_file(fixture / "fixture.json"),
    }
    engines: dict[str, dict[str, object]] = {}

    if upstream is not None:
        midi = _one_export(upstream, ".mid")
        svl = _one_export(upstream, ".svl")
        diagnostic = upstream / "diagnostico.json"
        padding, version = _diagnostic(diagnostic)
        upstream_notes = read_upstream_midi(midi)
        upstream_beats, upstream_downbeats = read_upstream_svl(svl, padding_seconds=padding)
        engines["auto_cdlc"] = _grade(truth, note_events=upstream_notes, beats=upstream_beats, downbeats=upstream_downbeats)
        engines["auto_cdlc"]["artifact_source_binding"] = "UNPROVEN"
        engines["auto_cdlc"]["reported_version"] = version
        input_hashes.update({
            "upstream_mid": sha256_file(midi),
            "upstream_svl": sha256_file(svl),
            "upstream_diagnostics": sha256_file(diagnostic),
        })

    if project is not None:
        manifest = ProjectManifest.load(project)
        relative = Path(manifest.source_project_path)
        source_copy = (project / relative).resolve()
        if relative.is_absolute() or not source_copy.is_relative_to(project) or not source_copy.is_file():
            raise KnownTruthError("Local project source is outside its immutable project boundary")
        if sha256_file(source_copy) != truth["source_audio_sha256"] or manifest.source_sha256 != truth["source_audio_sha256"]:
            raise KnownTruthError("Local project source does not match verified synthetic recording")
        bass_path = project / "analysis" / "bass_raw.json"
        tempo_path = project / "analysis" / "tempo_map.json"
        bass = read_transcription(bass_path)
        tempo = read_tempo_map(tempo_path)
        notes = [DiffNote(n.start, n.duration, n.midi) for n in bass.notes]
        beats = [b.time for b in tempo.beats]
        downbeats = [b.time for b in tempo.beats if b.is_downbeat]
        engines["our_generator"] = _grade(truth, note_events=notes, beats=beats, downbeats=downbeats)
        engines["our_generator"]["artifact_source_binding"] = "UNPROVEN"
        input_hashes.update({"local_bass": sha256_file(bass_path), "local_tempo": sha256_file(tempo_path)})

    all_ok = bool(engines) and all(e["fixture_verdict"] == "PASS" for e in engines.values())
    report: dict[str, object] = {
        "schema_version": 1,
        "kind": _KIND,
        "profile": PROFILE,
        "fixture_audio_integrity": "REGENERATED_AND_SHA256_MATCHED",
        "source_audio_sha256": truth["source_audio_sha256"],
        "comparison_verdict": "PASS" if all_ok else "FAIL",
        "scope": "SYNTHETIC_FIXTURE_ONLY",
        "real_song_accuracy_proven": False,
        "rocksmith_gameplay_proven": False,
        "producer_input_output_binding": "UNPROVEN",
        "engine_results": engines,
        "input_sha256": input_hashes,
        "build_identity": asdict(current_build_identity()),
    }
    _write_report(out_path, fixture=fixture, upstream=upstream, local_project=project, report=report)
    return report
