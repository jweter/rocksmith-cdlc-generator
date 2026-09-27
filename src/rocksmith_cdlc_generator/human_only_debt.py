from __future__ import annotations

from .private_product_reality import (
    PrivateProductRealityEvidence,
    automation_evidence_gaps,
    human_only_debt_items,
)


def _debt_category(item: str) -> str:
    normalized = item.lower()
    if any(token in normalized for token in ("feel", "play", "timing", "musical", "subjective")):
        return "SUBJECTIVE_MUSICAL_JUDGMENT"
    if any(token in normalized for token in ("rocksmith", "game", "load", "launch", "runtime")):
        return "PRIVATE_RUNTIME_ACCEPTANCE"
    if "review" in normalized:
        return "PENDING_HUMAN_REVIEW"
    return "HUMAN_REVIEW"


def human_only_debt_payload(
    evidence: PrivateProductRealityEvidence,
) -> dict[str, object]:
    """Return a sanitized machine-readable queue of genuinely human-only debt.

    ``items`` names only what still genuinely needs a person: the scenario's declared
    human-only acceptance plus the one evidence-derived case this repository currently
    proves is a real human task (printed-score pages awaiting human review). Deterministic
    REVIEW_REQUIRED checks are reported separately under ``automation_evidence_gaps``:
    missing/stale/unknown evidence fails closed but is never relabeled as human debt or
    silently treated as PASS.
    """
    items = human_only_debt_items(evidence)
    categorized_items = [
        {"category": _debt_category(item), "description": item}
        for item in items
    ]
    categories = sorted({item["category"] for item in categorized_items})
    return {
        "schema_version": 3,
        "build_commit_sha": evidence.build.commit_sha,
        "scenario_id": evidence.scenario_id,
        "human_attention_required": bool(items),
        "item_count": len(items),
        "categories": categories,
        "items": items,
        "categorized_items": categorized_items,
        "automation_evidence_gaps": automation_evidence_gaps(evidence),
    }
