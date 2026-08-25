from pathlib import Path

import pytest

import rocksmith_cdlc_generator.validation as bass_validation


def test_bass_score_coverage_is_optional_when_no_score_is_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_assessment(_project_dir: Path) -> None:
        raise AssertionError("coverage assessment should not run without a registered score")

    monkeypatch.setattr(
        bass_validation,
        "assess_project_score_coverage",
        unexpected_assessment,
    )
    items: list[bass_validation.ReviewItem] = []

    bass_validation._validate_score_coverage(items, tmp_path)

    assert items == []


def test_bass_score_coverage_fails_closed_when_registered_evidence_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    score_contract = tmp_path / "sources" / "score" / "source.json"
    score_contract.parent.mkdir(parents=True)
    score_contract.write_text("{}", encoding="utf-8")

    def invalid_assessment(_project_dir: Path) -> None:
        raise ValueError("stale score fan-out")

    monkeypatch.setattr(
        bass_validation,
        "assess_project_score_coverage",
        invalid_assessment,
    )
    items: list[bass_validation.ReviewItem] = []

    bass_validation._validate_score_coverage(items, tmp_path)

    assert len(items) == 1
    finding = items[0]
    assert finding.code == "invalid_score_coverage_evidence"
    assert finding.severity == "FAIL"
    assert finding.stage == "source_coverage"
    assert finding.priority == 100
    assert "stale score fan-out" in finding.message
