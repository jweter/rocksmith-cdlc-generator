"""CLI for the private corpus differential harness (issue #693 slice 6). Synthetic fixtures only."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from rocksmith_cdlc_generator.corpus_differential_cli import main

PITCHES = [40, 43, 45, 47, 48, 50, 52, 55]


def _notes(count: int = 20, spacing: float = 0.5, shift: float = 0.0) -> list[dict[str, object]]:
    return [
        {
            "onset_seconds": round(i * spacing + shift, 6),
            "duration_seconds": 0.4,
            "midi": PITCHES[i % len(PITCHES)],
        }
        for i in range(count)
    ]


def _write(path: Path, notes: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(notes), encoding="utf-8")
    return path


def _run(monkeypatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["cdlc-corpus-diff", *argv])
    main()


def test_pass_exits_zero(tmp_path: Path, monkeypatch, capsys) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes())
    out = tmp_path / "report.json"

    _run(
        monkeypatch,
        [
            "--reference", str(reference),
            "--generated", str(generated),
            "--trust-tier", "A",
            "--lane", "independent_generation",
            "--out", str(out),
        ],
    )

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["verdict"] == "PASS"
    assert "Verdict: PASS" in capsys.readouterr().out


def test_review_required_exits_three_for_a_tier_c_reference(tmp_path: Path, monkeypatch, capsys) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes())
    out = tmp_path / "report.json"

    with pytest.raises(SystemExit) as excinfo:
        _run(
            monkeypatch,
            [
                "--reference", str(reference),
                "--generated", str(generated),
                "--trust-tier", "C",
                "--lane", "importer_fidelity",
                "--out", str(out),
            ],
        )

    assert excinfo.value.code == 3
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["verdict"] == "REVIEW_REQUIRED"
    assert report["lane"] == "importer_fidelity"
    output = capsys.readouterr().out
    assert "do not report as independent generation accuracy" in output


def test_fail_exits_two(tmp_path: Path, monkeypatch) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes(shift=0.2))
    out = tmp_path / "report.json"

    with pytest.raises(SystemExit) as excinfo:
        _run(
            monkeypatch,
            [
                "--reference", str(reference),
                "--generated", str(generated),
                "--trust-tier", "A",
                "--lane", "independent_generation",
                "--out", str(out),
            ],
        )

    assert excinfo.value.code == 2
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "FAIL"


def test_malformed_input_exits_one_with_a_clear_error(tmp_path: Path, monkeypatch, capsys) -> None:
    reference = tmp_path / "reference.json"
    reference.write_text("not json", encoding="utf-8")
    generated = _write(tmp_path / "generated.json", _notes())
    out = tmp_path / "report.json"

    with pytest.raises(SystemExit) as excinfo:
        _run(
            monkeypatch,
            [
                "--reference", str(reference),
                "--generated", str(generated),
                "--trust-tier", "A",
                "--lane", "independent_generation",
                "--out", str(out),
            ],
        )

    assert excinfo.value.code == 1
    assert "error:" in capsys.readouterr().err
    assert not out.exists()


def test_output_inside_repository_checkout_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes())
    repo_root = Path(__file__).resolve().parents[1]
    in_repo_out = repo_root / "corpus-diff-report-should-not-be-written.json"
    assert not in_repo_out.exists()

    try:
        with pytest.raises(SystemExit) as excinfo:
            _run(
                monkeypatch,
                [
                    "--reference", str(reference),
                    "--generated", str(generated),
                    "--trust-tier", "A",
                    "--lane", "independent_generation",
                    "--out", str(in_repo_out),
                ],
            )
        assert excinfo.value.code == 1
        assert "repository checkout" in capsys.readouterr().err
        assert not in_repo_out.exists()
    finally:
        if in_repo_out.exists():  # pragma: no cover - safety net only
            in_repo_out.unlink()


def test_unknown_lane_is_rejected_by_argument_parsing(tmp_path: Path, monkeypatch) -> None:
    reference = _write(tmp_path / "reference.json", _notes())
    generated = _write(tmp_path / "generated.json", _notes())
    out = tmp_path / "report.json"

    with pytest.raises(SystemExit) as excinfo:
        _run(
            monkeypatch,
            [
                "--reference", str(reference),
                "--generated", str(generated),
                "--trust-tier", "A",
                "--lane", "generation_accuracy",
                "--out", str(out),
            ],
        )

    assert excinfo.value.code == 2  # argparse usage error
