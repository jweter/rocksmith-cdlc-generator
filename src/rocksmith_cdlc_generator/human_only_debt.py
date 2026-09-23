from __future__ import annotations

from .private_product_reality import PrivateProductRealityEvidence


def _debt_category(item: str) -> str:
    normalized = item.lower()
    if any(token in normalized for token in ("feel", "play", "timing", "musical", "subjective")):
        return "SUBJECTIVE_MUSICAL_JUDGMENT"
    if any(token in normalized for token in ("rocksmith", "game", "load", "launch", "runtime")):
        return "PRIVATE_RUNTIME_ACCEPTANCE"
    return "HUMAN_REVIEW"


def human_only_debt_payload(
    evidence: PrivateProductRealityEvidence,
) -> dict[str, object]:
    """Return a sanitized machine-readable queue of genuinely human-only debt."""
    items = list(evidence.human_only_acceptance)
    categorized_items = [
        {"category": _debt_category(item), "description": item}
        for item in items
    ]
    categories = sorted({item["category"] for item in categorized_items})
    return {
        "schema_version": 2,
        "build_commit_sha": evidence.build.commit_sha,
        "scenario_id": evidence.scenario_id,
        "human_attention_required": bool(items),
        "item_count": len(items),
        "categories": categories,
        "items": items,
        "categorized_items": categorized_items,
    }
