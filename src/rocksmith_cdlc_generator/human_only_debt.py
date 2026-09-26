"""Human-only Product Reality debt over private-runner evidence (issue #612).

Only subjective musical judgment or not-yet-automated Rocksmith runtime
acceptance is human debt. Measurable facts are covered or automation debt.
Missing or non-PASS evidence fails closed; check messages are never copied.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .score_source import ArrangementRole

if TYPE_CHECKING:
    from .private_product_reality import PrivateProductRealityEvidence

SCHEMA_VERSION = 3

STATUS_HUMAN_ATTENTION_REQUIRED = "HUMAN_ATTENTION_REQUIRED"
STATUS_NO_HUMAN_ATTENTION_REQUIRED = "NO_HUMAN_ATTENTION_REQUIRED"
STATUS_FAIL_CLOSED = "FAIL_CLOSED"

CATEGORY_SUBJECTIVE = "SUBJECTIVE_MUSICAL_JUDGMENT"
CATEGORY_EXTERNAL_RUNTIME = "EXTERNAL_ROCKSMITH_RUNTIME"

_ROLES = (ArrangementRole.bass.value, ArrangementRole.lead.value, ArrangementRole.rhythm.value)

_SUBJECTIVE = re.compile(
    r"\b(feel|feels|feeling|tone|comfort|comfortable|subjective|preference|prefer|"
    r"taste|musical|musically|fingering|ergonomic|ergonomics)\b"
)
_EXTERNAL_RUNTIME = re.compile(r"\b(rocksmith|in-game|in game|gameplay|game)\b")
_ROLE = re.compile(r"\b(bass|lead|rhythm)\b")

# Measurable vocabulary -> automated check codes (exact, "_"-suffixed prefix, or
# "{role}" template) that establish the fact; no codes means not measured here.
_DETERMINISTIC_RULES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\bfirst (playable|event|note)s?\b"), ("{role}_first_event",)),
    (re.compile(r"\bspread\b"), ("arrangement_first_event_spread",)),
    (re.compile(r"\b(checkpoints?|drift)\b"), ("checkpoint_",)),
    (re.compile(r"\b(beat grid|beat-grid|tempo map|tempo-map)\b"), ("audio_beat_grid",)),
    (
        re.compile(r"\b(timing|offset|sync|synchroni[sz]ed?|late|early|seconds?)\b"),
        ("shared_timing_transform",),
    ),
    (re.compile(r"\b(psarc registration|staged psarc)\b"), ("psarc_registration",)),
    (re.compile(r"\bofficial tab\b"), ("official_tab_registration",)),
    (re.compile(r"\bprinted[- ]score\b"), ("printed_score_recognition",)),
    (re.compile(r"\b(xml|note counts?|hash|hashes|sha-?256|validation)\b"), ()),
)


def _evidence_blockers(
    evidence: PrivateProductRealityEvidence | None, expected_commit_sha: str | None
) -> list[str]:
    if evidence is None:
        return ["evidence_missing"]
    blockers: list[str] = []
    if evidence.build.commit_sha is None:
        blockers.append("build_identity_unknown")
    elif expected_commit_sha is not None and evidence.build.commit_sha != expected_commit_sha:
        blockers.append("evidence_stale_build")
    if not evidence.checks:
        blockers.append("automated_checks_missing")
    elif evidence.result != "PASS" or any(check.status != "PASS" for check in evidence.checks):
        blockers.append("automated_evidence_not_pass")
    return blockers


def _code_passed(code: str, roles: list[str], passing: set[str]) -> bool:
    if "{role}" in code:
        # Named roles must each be measured; unnamed means every observed role.
        wanted = [code.format(role=role) for role in (roles or _ROLES)]
        present = [name for name in wanted if name in passing]
        return bool(present) and (not roles or len(present) == len(wanted))
    if code.endswith("_"):
        return any(name.startswith(code) for name in passing)
    return code in passing


def _classify(item: str, passing: set[str]) -> dict[str, object]:
    text = item.lower()
    roles = [role for role in _ROLES if role in set(_ROLE.findall(text))]
    rules = [codes for pattern, codes in _DETERMINISTIC_RULES if pattern.search(text)]
    subjective = bool(_SUBJECTIVE.search(text))
    external = bool(_EXTERNAL_RUNTIME.search(text))
    if rules and (subjective or external):
        return {"kind": "unclassified", "reason": "mixed_deterministic_and_human_terms"}
    if rules:
        covered = all(codes and all(_code_passed(c, roles, passing) for c in codes) for codes in rules)
        reason = "covered_by_automated_evidence" if covered else "automation_debt"
        return {"kind": "excluded", "reason": reason, "roles": roles}
    if subjective or external:
        category = CATEGORY_SUBJECTIVE if subjective else CATEGORY_EXTERNAL_RUNTIME
        return {"kind": "human", "category": category, "roles": roles}
    return {"kind": "unclassified", "reason": "no_recognized_human_or_deterministic_terms"}


def human_only_debt_payload(
    evidence: PrivateProductRealityEvidence | None,
    *,
    expected_commit_sha: str | None = None,
) -> dict[str, object]:
    """Return a sanitized machine-readable queue of genuinely human-only debt."""
    blockers = _evidence_blockers(evidence, expected_commit_sha)
    status_by_code = {} if evidence is None else {c.code: c.status for c in evidence.checks}
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "build_commit_sha": None if evidence is None else evidence.build.commit_sha,
        "scenario_id": None if evidence is None else evidence.scenario_id,
        "automated_result": None if evidence is None else evidence.result,
        "arrangement_coverage": {
            role: status_by_code.get(f"{role}_first_event", "NOT_OBSERVED") for role in _ROLES
        },
        "evidence_blockers": blockers,
        "blocking_check_codes": [code for code, status in status_by_code.items() if status != "PASS"],
    }
    buckets: dict[str, list[dict[str, object]]] = {"human": [], "excluded": [], "unclassified": []}
    if evidence is not None and not blockers:
        passing = {code for code, status in status_by_code.items() if status == "PASS"}
        for item in evidence.human_only_acceptance:
            result = _classify(item, passing)
            buckets[str(result.pop("kind"))].append({"description": item, **result})
    human = buckets["human"]
    fail_closed = bool(blockers or buckets["unclassified"])
    if fail_closed:
        # Without current PASS evidence and fully classified items nothing is human-only.
        human = []
    payload.update(
        {
            "status": STATUS_FAIL_CLOSED
            if fail_closed
            else (STATUS_HUMAN_ATTENTION_REQUIRED if human else STATUS_NO_HUMAN_ATTENTION_REQUIRED),
            "human_attention_required": None if fail_closed else bool(human),
            "item_count": len(human),
            "categories": sorted({str(entry["category"]) for entry in human}),
            "items": [str(entry["description"]) for entry in human],
            "categorized_items": human,
            "excluded_items": buckets["excluded"],
            "unclassified_items": buckets["unclassified"],
        }
    )
    return payload


def format_human_only_debt_section(payload: dict[str, object]) -> list[str]:
    """Render the human-only debt section of the runner text report."""
    if payload["status"] == STATUS_FAIL_CLOSED:
        reasons = list(payload["evidence_blockers"])  # type: ignore[arg-type]
        if payload["unclassified_items"]:
            reasons.append("unclassified_acceptance_items")
        lines = ["Human-only acceptance debt: UNKNOWN (fail closed: " + ", ".join(reasons) + ")"]
        lines.extend(f"- unclassified: {e['description']}" for e in payload["unclassified_items"])  # type: ignore[union-attr]
        return lines
    if payload["status"] == STATUS_NO_HUMAN_ATTENTION_REQUIRED:
        lines = ["Human-only acceptance debt: none"]
    else:
        lines = ["Human-only acceptance debt:"]
        lines.extend(f"- {item}" for item in payload["items"])  # type: ignore[union-attr]
    for entry in payload["excluded_items"]:  # type: ignore[union-attr]
        lines.append(f"- not human debt ({entry['reason']}): {entry['description']}")
    return lines
