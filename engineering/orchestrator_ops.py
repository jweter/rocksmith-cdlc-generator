from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "engineering" / "control-plane.json"
PRIVATE_EVIDENCE_DIR = ROOT / "private" / "product-reality-evidence"
PUBLIC_ATTESTATIONS = ROOT / "engineering" / "product-reality-attestations.json"


def load_control() -> dict[str, Any]:
    return json.loads(CONTROL.read_text(encoding="utf-8"))


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def git_head() -> str:
    return git_value("rev-parse", "HEAD")


def git_tree() -> str:
    return git_value("rev-parse", "HEAD^{tree}")


def verify_preflight(path: Path) -> int:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    control = load_control()
    expected_repo = control["repository"]
    expected_head = git_head()
    errors: list[str] = []
    if evidence.get("repository") != expected_repo:
        errors.append("repository mismatch")
    if evidence.get("head_sha") != expected_head:
        errors.append("head SHA mismatch")
    if evidence.get("mode") != "FULL":
        errors.append("evidence is not FULL preflight")
    if evidence.get("status") != "GREEN":
        errors.append("preflight is not GREEN")
    if errors:
        print(json.dumps({"status": "REJECTED", "errors": errors}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": "PREFLIGHT_GREEN",
                "repository": expected_repo,
                "head_sha": expected_head,
            },
            indent=2,
        )
    )
    return 0


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return value or "evidence"


def load_attestations(repository: str) -> dict[str, Any]:
    if not PUBLIC_ATTESTATIONS.exists():
        return {"schema_version": 1, "repository": repository, "lanes": {}}
    payload = json.loads(PUBLIC_ATTESTATIONS.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("repository") != repository:
        raise SystemExit("Product Reality attestation file has invalid repository/schema identity")
    if not isinstance(payload.get("lanes"), dict):
        raise SystemExit("Product Reality attestation lanes must be an object")
    return payload


def record_product_reality(args: argparse.Namespace) -> int:
    control = load_control()
    repository = control["repository"]
    allowed = set(control.get("verification", {}).get("product_reality_lanes", []))
    if args.lane not in allowed:
        raise SystemExit(f"Unknown Product Reality lane: {args.lane}")
    status = args.status.upper()
    if status not in {"PASS", "FAIL", "PENDING", "BLOCKED"}:
        raise SystemExit("status must be PASS, FAIL, PENDING, or BLOCKED")
    if status == "PASS" and not args.evidence:
        raise SystemExit("PASS requires at least one concrete --evidence reference")

    recorded_at = datetime.now(UTC).isoformat()
    record = {
        "schema_version": 1,
        "repository": repository,
        "lane": args.lane,
        "status": status,
        "head_sha": args.head_sha or git_head(),
        "tree_sha": git_tree(),
        "recorded_at": recorded_at,
        "actor": args.actor,
        "summary": args.summary,
        "evidence": args.evidence or [],
        "residual_risk": args.residual_risk,
    }
    PRIVATE_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    private_path = PRIVATE_EVIDENCE_DIR / f"{stamp}-{slug(args.lane)}.json"
    private_bytes = (json.dumps(record, indent=2) + "\n").encode()
    private_path.write_bytes(private_bytes)

    attestations = load_attestations(repository)
    attestations["lanes"][args.lane] = {
        "status": status,
        "head_sha": record["head_sha"],
        "tree_sha": record["tree_sha"],
        "recorded_at": recorded_at,
        "private_record_sha256": hashlib.sha256(private_bytes).hexdigest(),
    }
    PUBLIC_ATTESTATIONS.write_text(
        json.dumps(attestations, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"private evidence: {private_path.relative_to(ROOT)}")
    print(f"redacted attestation: {PUBLIC_ATTESTATIONS.relative_to(ROOT)}")
    return 0


def github_json(path: str) -> Any:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise SystemExit("GITHUB_TOKEN and GITHUB_REPOSITORY are required")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "control-plane-reconciler",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def github_pages(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    separator = "&" if "?" in path else "?"
    for page in range(1, 101):
        batch = github_json(f"{path}{separator}per_page=100&page={page}")
        if not isinstance(batch, list):
            raise SystemExit(f"Expected a list from GitHub API path {path}")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise SystemExit(f"GitHub pagination exceeded safety limit for {path}")


def reconcile_status(output: Path) -> int:
    control = load_control()
    repository = control["repository"]
    pulls = github_pages("/pulls?state=open")
    issues = github_pages("/issues?state=open")
    issue_numbers = sorted(
        item["number"] for item in issues if "pull_request" not in item
    )
    pr_rows = sorted(
        (
            {
                "number": item["number"],
                "draft": bool(item.get("draft")),
                "head": item["head"]["ref"],
                "base": item["base"]["ref"],
            }
            for item in pulls
            if item["head"]["ref"] != "automation/status-reconcile"
        ),
        key=lambda row: row["number"],
    )

    product_reality = {
        lane: "PENDING"
        for lane in control.get("verification", {}).get("product_reality_lanes", [])
    }
    attestations = load_attestations(repository)
    current_tree = git_tree()
    for lane, row in attestations["lanes"].items():
        if lane not in product_reality or not isinstance(row, dict):
            continue
        status = row.get("status")
        if status not in {"PASS", "FAIL", "PENDING", "BLOCKED"}:
            continue
        if row.get("tree_sha") != current_tree:
            product_reality[lane] = "STALE"
        else:
            product_reality[lane] = status

    readiness_dimensions = control.get("readiness_scoring", {}).get("dimensions", [])
    snapshot = {
        "schema_version": 1,
        "repository": repository,
        "open_pull_requests": pr_rows,
        "open_issue_numbers": issue_numbers,
        "product_reality": product_reality,
        "readiness_dimensions": {key: "UNKNOWN" for key in readiness_dimensions},
        "rule": (
            "Generated from live GitHub state and redacted Product Reality attestations; "
            "private Product Reality reports never enter Git, and stale build evidence is "
            "reported as STALE rather than PASS."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Control-plane orchestration utilities.")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify-preflight")
    verify.add_argument("--evidence", default="preflight-evidence.json")

    record = sub.add_parser("record-product-reality")
    record.add_argument("--lane", required=True)
    record.add_argument("--status", required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--actor", default="human")
    record.add_argument("--head-sha")
    record.add_argument("--evidence", action="append")
    record.add_argument("--residual-risk")

    reconcile = sub.add_parser("reconcile-status")
    reconcile.add_argument("--output", default="engineering/live-status.json")

    args = parser.parse_args()
    if args.command == "verify-preflight":
        return verify_preflight(ROOT / args.evidence)
    if args.command == "record-product-reality":
        return record_product_reality(args)
    return reconcile_status(ROOT / args.output)


if __name__ == "__main__":
    raise SystemExit(main())
