from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import private_product_reality
from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    PrivateProductRealityScenario,
    RoleTimingObservation,
    SharedTimingExpectations,
    SharedTimingObservation,
    collect_shared_timing_observation,
    evaluate_shared_timing_observation,
)
from rocksmith_cdlc_generator.product_reality_xml_validation import (
    XmlStructuralProductRealityEvidence,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole

HASH = "a" * 64


def _scenario(tmp_path: Path) -> PrivateProductRealityScenario:
    return PrivateProductRealityScenario(
        scenario_id="xml-validation-runner-integration",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass],
        expected=SharedTimingExpectations(first_playable_seconds=1.0),
    )


def _observation(
    scenario: PrivateProductRealityScenario,
    xml_structural_validation: XmlStructuralProductRealityEvidence | None,
) -> SharedTimingObservation:
    return SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(scenario.project_dir),
        observed_at_utc="2026-11-11T00:40:00+00:00",
        build=BuildObservation(version="test", commit_sha="b" * 40, packaged=True),
        tempo_beat_count=2,
        roles=[
            RoleTimingObservation(
                role=ArrangementRole.bass,
                source_track_index=0,
                first_source_seconds=1.0,
                first_playable_seconds=1.0,
                note_count=1,
                recording_sha256=HASH,
                score_sha256=HASH,
                source_output_sha256=HASH,
                timing_points_sha256=HASH,
            )
        ],
        xml_structural_validation=xml_structural_validation,
    )


def test_passing_xml_structural_validation_becomes_a_deterministic_pass_check(
    tmp_path: Path,
) -> None:
    scenario = _scenario(tmp_path)
    validation = XmlStructuralProductRealityEvidence(
        status="PASS",
        roles_checked=["bass_xml"],
        message="Staged arrangement XML (bass_xml) is structurally self-consistent.",
    )

    evidence = evaluate_shared_timing_observation(
        scenario, _observation(scenario, validation), scenario_sha256=HASH
    )

    check = next(
        item for item in evidence.checks if item.code == "xml_structural_validation"
    )
    assert check.status == "PASS"
    assert evidence.xml_structural_validation == validation
    assert evidence.result == "PASS"


def test_failing_xml_structural_validation_fails_the_scenario_automatically(
    tmp_path: Path,
) -> None:
    scenario = _scenario(tmp_path)
    validation = XmlStructuralProductRealityEvidence(
        status="FAIL",
        roles_checked=["bass_xml"],
        message="Staged arrangement XML failed structural self-consistency: bass_xml (1).",
    )

    evidence = evaluate_shared_timing_observation(
        scenario, _observation(scenario, validation), scenario_sha256=HASH
    )

    check = next(
        item for item in evidence.checks if item.code == "xml_structural_validation"
    )
    assert check.status == "FAIL"
    assert evidence.result == "FAIL"


def test_no_staged_build_adds_no_check_and_does_not_block_a_pure_timing_scenario(
    tmp_path: Path,
) -> None:
    scenario = _scenario(tmp_path)

    evidence = evaluate_shared_timing_observation(
        scenario, _observation(scenario, None), scenario_sha256=HASH
    )

    assert not any(
        item.code == "xml_structural_validation" for item in evidence.checks
    )
    assert evidence.result == "PASS"


def test_collect_shared_timing_observation_skips_xml_check_when_never_staged(
    tmp_path: Path,
) -> None:
    scenario = _scenario(tmp_path)

    observation = collect_shared_timing_observation(scenario)

    assert observation.xml_structural_validation is None
    assert not any(
        "staged arrangement XML" in error for error in observation.collection_errors
    )


def test_collect_shared_timing_observation_wires_in_xml_structural_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _scenario(tmp_path)
    readiness = tmp_path / "build" / "staging" / "build_readiness.json"
    readiness.parent.mkdir(parents=True)
    readiness.write_text("{}", encoding="utf-8")
    validation = XmlStructuralProductRealityEvidence(
        status="PASS",
        roles_checked=["bass_xml"],
        message="Staged arrangement XML (bass_xml) is structurally self-consistent.",
    )
    monkeypatch.setattr(
        private_product_reality,
        "collect_xml_structural_validation_evidence",
        lambda project: validation,
    )

    observation = collect_shared_timing_observation(scenario)

    assert observation.xml_structural_validation == validation


def test_collect_shared_timing_observation_reports_unreadable_xml_as_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _scenario(tmp_path)
    readiness = tmp_path / "build" / "staging" / "build_readiness.json"
    readiness.parent.mkdir(parents=True)
    readiness.write_text("{}", encoding="utf-8")

    def _broken(_project: Path) -> XmlStructuralProductRealityEvidence:
        raise OSError("staged xml disk read failed")

    monkeypatch.setattr(
        private_product_reality, "collect_xml_structural_validation_evidence", _broken
    )

    observation = collect_shared_timing_observation(scenario)

    assert observation.xml_structural_validation is None
    assert any(
        "staged arrangement XML is unreadable" in error
        for error in observation.collection_errors
    )
