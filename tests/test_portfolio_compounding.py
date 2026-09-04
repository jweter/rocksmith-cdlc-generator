from __future__ import annotations

import json

from engineering.portfolio_compounding import (
    UNKNOWN,
    aggregate,
    collapse_components,
    geometric_mean,
    load_reports,
)


def report(**values: float | str) -> dict[str, object]:
    return {"evidence_derived": values}


def test_geometric_mean_rejects_empty_and_nonpositive_values() -> None:
    assert geometric_mean([]) == UNKNOWN
    assert geometric_mean([1.0, 0.0]) == UNKNOWN
    assert geometric_mean([1.0, 4.0]) == 2.0


def test_aggregate_requires_complete_coverage_per_dimension() -> None:
    reports = {
        "knowledge-engine": report(
            throughput_factor=2.0,
            cycle_time_factor=2.0,
            engineering_multiplication_factor=4.0,
        ),
        "rocksmith": report(
            throughput_factor=0.5,
            cycle_time_factor=2.0,
            engineering_multiplication_factor=1.0,
        ),
        "everward": report(
            throughput_factor=1.0,
            cycle_time_factor=2.0,
            engineering_multiplication_factor=2.0,
        ),
    }
    result = aggregate(reports)
    assert result["evidence_derived"]["throughput_factor"] == 1.0
    assert result["evidence_derived"]["cycle_time_factor"] == 2.0
    assert result["evidence_derived"]["engineering_multiplication_factor"] == 2.0
    assert result["evidence_derived"]["repeat_failure_factor"] == UNKNOWN
    assert result["portfolio_signal"] == "COMPOUNDING_SIGNAL"


def test_missing_project_evidence_forces_unknown_dimension() -> None:
    reports = {
        "a": report(engineering_multiplication_factor=2.0),
        "b": report(engineering_multiplication_factor=UNKNOWN),
    }
    result = aggregate(reports)
    assert result["evidence_derived"]["engineering_multiplication_factor"] == UNKNOWN
    assert result["portfolio_signal"] == UNKNOWN
    assert result["coverage"]["engineering_multiplication_factor"]["missing_projects"] == [
        "b"
    ]


def test_knowledge_engine_components_collapse_to_one_project(tmp_path) -> None:
    paths = []
    for name, emf in (("core", 4.0), ("web", 1.0), ("ai", 2.0)):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "evidence_derived": {
                        "throughput_factor": 1.0,
                        "cycle_time_factor": 1.0,
                        "engineering_multiplication_factor": emf,
                    }
                }
            ),
            encoding="utf-8",
        )
        paths.append(f"knowledge-engine/{name}={path}")

    collapsed = collapse_components(paths)
    assert list(collapsed) == ["knowledge-engine"]
    assert collapsed["knowledge-engine"]["components"] == ["ai", "core", "web"]
    assert (
        collapsed["knowledge-engine"]["evidence_derived"][
            "engineering_multiplication_factor"
        ]
        == 2.0
    )


def test_duplicate_direct_and_component_project_is_rejected_by_contract(tmp_path) -> None:
    direct = tmp_path / "direct.json"
    component = tmp_path / "component.json"
    payload = {"evidence_derived": {"engineering_multiplication_factor": 1.0}}
    direct.write_text(json.dumps(payload), encoding="utf-8")
    component.write_text(json.dumps(payload), encoding="utf-8")

    reports = load_reports([f"knowledge-engine={direct}"])
    collapsed = collapse_components([f"knowledge-engine/core={component}"])
    assert set(reports) & set(collapsed) == {"knowledge-engine"}
