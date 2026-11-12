"""Corpus differential harness (issue #693 slice 6): sanitization, lanes, and the output guard.

All fixtures are synthetic; no private song material, PSARC, or audio is read or committed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.corpus_differential_harness import (
    CorpusDifferentialHarnessError,
    load_diff_notes,
    refuse_output_inside_repository_checkout,
    run_corpus_differential_harness,
)

PITCHES = [40, 43, 45, 47, 48, 50, 52, 55]


def _notes(count: int = 20, spacing: float = 0.5, shift: float = 0.0) -> list[dict[str, object]]:
    return [
        {
            "onset_seconds": round(i * spacing + shift, 6),
            "duration_seconds": 0.4,
            "midi": PITCHES[i % len(PITCHES)],
            "string": i % 4,
            "fret": i % 12,
        }
        for i in range(count)
    ]


def _write(path: Path, notes: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(notes), encoding="utf-8")
    return path


def test_identical_arrangements_pass_and_the_report_is_sanitized(tmp_path: Path) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes())
    out = tmp_path / "report.json"

    differential, report, resolved_out = run_corpus_differential_harness(
        reference_path=reference,
        generated_path=generated,
        trust_tier="A",
        lane="independent_generation",
        out_path=out,
    )

    assert differential.verdict == "PASS"
    assert resolved_out == out.resolve()
    written = json.loads(resolved_out.read_text(encoding="utf-8"))
    assert written == report
    assert set(report) == {
        "trust_tier", "authoritative", "verdict", "reasons", "counts",
        "first_event_phase_seconds", "onset_phase_seconds", "onset_drift_seconds_per_minute",
        "onset_jitter_seconds", "onset_outlier_fraction", "recall", "precision",
        "pitch_agreement", "string_fret_agreement", "duration_agreement",
        "lane", "input_sha256", "build_identity",
    }
    assert report["lane"] == "independent_generation"
    assert set(report["input_sha256"]) == {"reference", "generated"}
    assert all(len(value) == 64 for value in report["input_sha256"].values())
    assert "version" in report["build_identity"]
    serialized = json.dumps(report)
    assert str(reference) not in serialized and str(generated) not in serialized
    assert str(tmp_path) not in serialized


def test_importer_fidelity_lane_is_labelled_and_not_independent_generation(tmp_path: Path) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes())
    out = tmp_path / "report.json"

    _differential, report, _resolved_out = run_corpus_differential_harness(
        reference_path=reference,
        generated_path=generated,
        trust_tier="B",
        lane="importer_fidelity",
        out_path=out,
    )

    assert report["lane"] == "importer_fidelity"
    assert report["lane"] != "independent_generation"


def test_output_is_refused_inside_the_repository_checkout() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / ".git").exists()

    with pytest.raises(CorpusDifferentialHarnessError):
        refuse_output_inside_repository_checkout(repo_root / "private-results" / "report.json")


def test_output_refusal_happens_before_any_input_file_is_read(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    missing_reference = tmp_path / "does-not-exist-reference.json"
    missing_generated = tmp_path / "does-not-exist-generated.json"

    with pytest.raises(CorpusDifferentialHarnessError, match="repository checkout"):
        run_corpus_differential_harness(
            reference_path=missing_reference,
            generated_path=missing_generated,
            trust_tier="A",
            lane="independent_generation",
            out_path=repo_root / "report.json",
        )


@pytest.mark.parametrize(
    "payload",
    [
        "not json at all {{{",
        "{}",
        "[1, 2, 3]",
        json.dumps([{"duration_seconds": 0.4, "midi": 40}]),
        json.dumps([{"onset_seconds": "soon", "duration_seconds": 0.4, "midi": 40}]),
        json.dumps([{"onset_seconds": -1.0, "duration_seconds": 0.4, "midi": 40}]),
    ],
)
def test_malformed_note_files_are_refused_with_a_clear_error(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "notes.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(CorpusDifferentialHarnessError):
        load_diff_notes(path)


def test_optional_string_and_fret_default_to_none(tmp_path: Path) -> None:
    path = tmp_path / "notes.json"
    path.write_text(json.dumps([{"onset_seconds": 0.0, "duration_seconds": 0.4, "midi": 40}]), encoding="utf-8")

    notes = load_diff_notes(path)

    assert notes[0].string is None and notes[0].fret is None


@pytest.mark.parametrize("lane", ["independent_generation", "importer_fidelity"])
def test_both_lanes_run_the_same_comparator(tmp_path: Path, lane: str) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes(shift=0.2))
    out = tmp_path / "report.json"

    differential, report, _resolved_out = run_corpus_differential_harness(
        reference_path=reference,
        generated_path=generated,
        trust_tier="A",
        lane=lane,
        out_path=out,
    )

    assert differential.verdict == "FAIL"
    assert report["verdict"] == "FAIL"
    assert report["lane"] == lane
