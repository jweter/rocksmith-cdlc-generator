from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_EVIDENCE_DIR = ROOT / "private" / "product-reality-evidence"

def load_private_evidence() -> Dict[str, Any]:
    evidence_path = PRIVATE_EVIDENCE_DIR / "human-only-debt.json"
    if evidence_path.exists():
        return json.loads(evidence_path.read_text(encoding="utf-8"))
    return {}

def save_private_evidence(evidence: Dict[str, Any]) -> None:
    evidence_path = PRIVATE_EVIDENCE_DIR / "human-only-debt.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

def generate_human_only_debt_report() -> Dict[str, Any]:
    evidence = load_private_evidence()
    report = {
        "schema_version": 1,
        "repository": "jweter/rocksmith-cdlc-generator",
        "generated_at": datetime.now().isoformat(),
        "human_only_debt": []
    }

    for lane, details in evidence.items():
        if details.get("status") == "PENDING":
            report["human_only_debt"].append({
                "lane": lane,
                "status": "PENDING",
                "summary": details.get("summary", "No summary provided")
            })

    return report

def record_human_only_debt(lane: str, status: str, summary: str) -> None:
    evidence = load_private_evidence()
    evidence[lane] = {
        "status": status,
        "summary": summary,
        "recorded_at": datetime.now().isoformat()
    }
    save_private_evidence(evidence)

def validate_human_only_debt() -> None:
    report = generate_human_only_debt_report()
    print(json.dumps(report, indent=2))
