from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN"


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def geometric_mean(values: list[float]) -> float | str:
    if not values or any(value <= 0 for value in values):
        return UNKNOWN
    product = 1.0
    for value in values:
        product *= value
    return round(product ** (1.0 / len(values)), 4)


def aggregate(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    dimensions = [
        "throughput_factor",
        "cycle_time_factor",
        "engineering_multiplication_factor",
        "repeat_failure_factor",
        "autonomous_completion_factor",
        "dependency_unlock_factor",
        "human_intervention_factor",
    ]
    aggregated: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    for dimension in dimensions:
        observed: list[float] = []
        missing: list[str] = []
        for name, report in reports.items():
            value = numeric((report.get("evidence_derived") or {}).get(dimension))
            if value is None:
                missing.append(name)
            else:
                observed.append(value)
        aggregated[dimension] = geometric_mean(observed) if not missing else UNKNOWN
        coverage[dimension] = {
            "observed_projects": len(observed),
            "expected_projects": len(reports),
            "missing_projects": missing,
        }

    portfolio_emf = aggregated["engineering_multiplication_factor"]
    claim = "UNKNOWN"
    if isinstance(portfolio_emf, float):
        claim = "COMPOUNDING_SIGNAL" if portfolio_emf > 1.0 else "NO_COMPOUNDING_SIGNAL"

    return {
        "schema_version": 1,
        "projects": sorted(reports),
        "project_count": len(reports),
        "evidence_derived": aggregated,
        "coverage": coverage,
        "portfolio_signal": claim,
        "claim_rule": (
            "A portfolio signal is descriptive, not proof of exponential development. "
            "Every dimension requires complete project coverage; sustained compounding "
            "requires comparable evidence across at least three windows."
        ),
    }


def load_reports(paths: list[str]) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for item in paths:
        name, separator, filename = item.partition("=")
        if not separator or not name or not filename:
            raise SystemExit("--report entries must be NAME=PATH")
        with Path(filename).open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise SystemExit(f"{filename} is not a JSON object")
        reports[name] = payload
    return reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.report:
        raise SystemExit("at least one --report NAME=PATH is required")
    payload = json.dumps(aggregate(load_reports(args.report)), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
