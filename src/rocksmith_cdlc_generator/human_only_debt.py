from __future__ import annotations

from .private_product_reality import PrivateProductRealityEvidence


def human_only_debt_payload(
    evidence: PrivateProductRealityEvidence,
) -> dict[str, object]:
    """Return a sanitized machine-readable queue of genuinely human-only debt."""
    items = list(evidence.human_only_acceptance)
    return {
        "schema_version": 1,
        "build_commit_sha": evidence.build.commit_sha,
        "scenario_id": evidence.scenario_id,
        "human_attention_required": bool(items),
        "item_count": len(items),
        "items": items,
    }
