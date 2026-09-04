from __future__ import annotations

import argparse
import json
import os
import statistics
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

UNKNOWN = "UNKNOWN"


def github_json(path: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY are required")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "engineering-compounding-metrics",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github_pages(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    separator = "&" if "?" in path else "?"
    for page in range(1, 21):
        batch = github_json(f"{path}{separator}per_page=100&page={page}")
        if not isinstance(batch, list):
            raise SystemExit(f"Expected list response for {path}")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise SystemExit(f"Pagination safety limit exceeded for {path}")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def window_metrics(
    pulls: list[dict[str, Any]], start: datetime, end: datetime
) -> dict[str, Any]:
    merged = []
    cycle_hours = []
    for pull in pulls:
        merged_at = parse_time(pull.get("merged_at"))
        created_at = parse_time(pull.get("created_at"))
        if merged_at is None or not (start <= merged_at < end):
            continue
        merged.append(pull)
        if created_at is not None:
            cycle_hours.append((merged_at - created_at).total_seconds() / 3600)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "merged_prs": len(merged),
        "median_pr_cycle_hours": (
            round(statistics.median(cycle_hours), 2) if cycle_hours else UNKNOWN
        ),
        "sample_size": len(merged),
    }


def safe_ratio(numerator: Any, denominator: Any) -> float | str:
    if (
        isinstance(numerator, bool)
        or isinstance(denominator, bool)
        or not isinstance(numerator, (int, float))
        or not isinstance(denominator, (int, float))
        or denominator <= 0
    ):
        return UNKNOWN
    return round(numerator / denominator, 4)


def build_report(days: int, now: datetime) -> dict[str, Any]:
    pulls = github_pages(f"/pulls?state=closed&sort=updated&direction=desc")
    current = window_metrics(pulls, now - timedelta(days=days), now)
    previous = window_metrics(
        pulls, now - timedelta(days=2 * days), now - timedelta(days=days)
    )
    older = window_metrics(
        pulls, now - timedelta(days=3 * days), now - timedelta(days=2 * days)
    )

    throughput_factor = safe_ratio(current["merged_prs"], previous["merged_prs"])
    prior_throughput_factor = safe_ratio(previous["merged_prs"], older["merged_prs"])
    cycle_time_factor = safe_ratio(
        previous["median_pr_cycle_hours"], current["median_pr_cycle_hours"]
    )
    emf = UNKNOWN
    if isinstance(throughput_factor, float) and isinstance(cycle_time_factor, float):
        emf = round(throughput_factor * cycle_time_factor, 4)

    compounding_rate = UNKNOWN
    if isinstance(throughput_factor, float) and isinstance(prior_throughput_factor, float):
        compounding_rate = safe_ratio(throughput_factor, prior_throughput_factor)
        if isinstance(compounding_rate, float):
            compounding_rate = round(compounding_rate - 1.0, 4)

    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "window_days": days,
        "windows": {"current": current, "previous": previous, "older": older},
        "evidence_derived": {
            "throughput_factor": throughput_factor,
            "cycle_time_factor": cycle_time_factor,
            "engineering_multiplication_factor": emf,
            "compounding_rate": compounding_rate,
        },
        "not_yet_measured": {
            "repeat_failure_rate": UNKNOWN,
            "autonomous_completion_rate": UNKNOWN,
            "dependency_unlock_rate": UNKNOWN,
            "human_intervention_rate": UNKNOWN,
        },
        "interpretation": (
            "These are descriptive GitHub-history metrics, not proof of exponential "
            "growth. Compounding requires sustained positive evidence across multiple "
            "windows. UNKNOWN is mandatory when evidence is insufficient."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.window_days <= 0:
        raise SystemExit("--window-days must be positive")
    report = build_report(args.window_days, datetime.now(UTC))
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
