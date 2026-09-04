from __future__ import annotations

from engineering.portfolio_compounding import UNKNOWN, aggregate, geometric_mean


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
