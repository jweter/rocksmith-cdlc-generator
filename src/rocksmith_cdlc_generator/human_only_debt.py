"""Fail-closed human-only Product Reality debt report (issue #612).

Only subjective or external-runtime items reach a person. Items naming a check
the runner already automates are excluded when that check PASSed and block the
report otherwise; unclassified items, and missing, stale, or non-PASS evidence,
block the report. Output carries check codes/statuses and scenario item text
only, never check messages, paths, hashes, or source material.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .private_product_reality import PrivateProductRealityEvidence
from .score_source import ArrangementRole

_HUMAN_CATEGORIES = ("SUBJECTIVE_MUSICAL_JUDGMENT", "PRIVATE_RUNTIME_ACCEPTANCE")
_ROLE_SCOPED = "{role}_first_event"
# Deterministic topics mapped to the check codes that cover them.
_DETERMINISTIC_TOPICS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("first note", "first event", "first-event", "first playable", "offset"), (_ROLE_SCOPED,)),
    (("spread",), ("arrangement_first_event_spread",)),
    (("shared timing", "timing transform", "same recording"), ("shared_timing_transform",)),
    (("checkpoint", "drift"), ("checkpoint_*",)),
    (("beat grid", "tempo map"), ("audio_beat_grid",)),
    (("build identity", "build commit"), ("build_identity",)),
    (("psarc registration", "psarc receipt"), ("psarc_registration",)),
    (("official tab",), ("official_tab_registration",)),
    (("printed score", "printed-score", "score recognition"), ("printed_score_recognition",)),
)
_SUBJECTIVE_TOKENS = ("feel", "playability", "musical", "subjective", "taste", "phrasing")
_RUNTIME_TOKENS = ("in-game", "in game", "gameplay", "rocksmith", "launch", "runtime")
_ROLE_PATTERN = re.compile(r"\b(" + "|".join(role.value for role in ArrangementRole) + r")\b")


def _required_check_codes(
    patterns: tuple[str, ...], roles: list[str], evidence: PrivateProductRealityEvidence
) -> list[str]:
    present = [check.code for check in evidence.checks]
    codes: list[str] = []
    for pattern in patterns:
        if pattern == _ROLE_SCOPED:
            # Each role is judged by its own evidence; unscoped items need every evaluated role.
            scoped = roles or [r.value for r in ArrangementRole if pattern.format(role=r.value) in present]
            codes.extend(pattern.format(role=role) for role in scoped)
        elif pattern.endswith("*"):
            # An absent wildcard family means the topic was never measured.
            codes.extend(sorted(c for c in present if c.startswith(pattern[:-1])) or [pattern])
        else:
            codes.append(pattern)
    return codes


def classify_human_only_item(item: str, evidence: PrivateProductRealityEvidence) -> dict[str, object]:
    """Classify one scenario-authored acceptance item against automated evidence."""
    normalized = item.lower()
    roles = sorted(set(_ROLE_PATTERN.findall(normalized)))
    status_by_code = {check.code: check.status for check in evidence.checks}
    for tokens, patterns in _DETERMINISTIC_TOPICS:
        if any(token in normalized for token in tokens):
            codes = _required_check_codes(patterns, roles, evidence)
            statuses = {code: status_by_code.get(code, "MISSING") for code in codes}
            return {
                "category": "AUTOMATED_DETERMINISTIC", "description": item, "roles": roles,
                "covering_checks": statuses,
                "covered_by_automation": bool(codes) and all(s == "PASS" for s in statuses.values()),
            }
    if any(token in normalized for token in _SUBJECTIVE_TOKENS):
        category = "SUBJECTIVE_MUSICAL_JUDGMENT"
    elif any(token in normalized for token in _RUNTIME_TOKENS):
        category = "PRIVATE_RUNTIME_ACCEPTANCE"
    else:
        category = "UNCLASSIFIED"
    return {"category": category, "description": item, "roles": roles}


def _evidence_blockers(
    evidence: PrivateProductRealityEvidence | None,
    current_commit_sha: str | None,
    now: datetime | None,
    max_age: timedelta | None,
) -> list[str]:
    if evidence is None:
        return ["EVIDENCE_MISSING"]
    blockers: list[str] = []
    if not evidence.build.commit_sha:
        blockers.append("EVIDENCE_BUILD_UNKNOWN")
    elif not current_commit_sha:
        blockers.append("CURRENT_BUILD_UNKNOWN")
    elif evidence.build.commit_sha != current_commit_sha:
        blockers.append("EVIDENCE_STALE_BUILD")
    if max_age is not None:
        try:
            observed = datetime.fromisoformat(evidence.observed_at_utc.replace("Z", "+00:00"))
        except ValueError:
            observed = None
        if observed is None or observed.tzinfo is None:
            blockers.append("EVIDENCE_TIME_UNKNOWN")
        elif (now or datetime.now(timezone.utc)) - observed > max_age:
            blockers.append("EVIDENCE_STALE_AGE")
    if not evidence.checks:
        blockers.append("AUTOMATED_EVIDENCE_EMPTY")
    elif evidence.result != "PASS":
        blockers.append(f"AUTOMATED_EVIDENCE_{evidence.result}")
    elif any(check.status != "PASS" for check in evidence.checks):
        blockers.append("AUTOMATED_EVIDENCE_INCONSISTENT")
    return blockers


def human_only_debt_payload(
    evidence: PrivateProductRealityEvidence | None,
    *,
    current_commit_sha: str | None,
    now: datetime | None = None,
    max_age: timedelta | None = None,
) -> dict[str, object]:
    """Return a sanitized report; status is CLEAR, HUMAN_ATTENTION_REQUIRED, or BLOCKED, never PASS."""
    blockers = _evidence_blockers(evidence, current_commit_sha, now, max_age)
    classified = (
        [] if evidence is None
        else [classify_human_only_item(item, evidence) for item in evidence.human_only_acceptance]
    )
    human_items = [i for i in classified if i["category"] in _HUMAN_CATEGORIES]
    deterministic = [i for i in classified if i["category"] == "AUTOMATED_DETERMINISTIC"]
    automation_debt = [i for i in deterministic if not i["covered_by_automation"]]
    unclassified = [i for i in classified if i["category"] == "UNCLASSIFIED"]
    if automation_debt:
        blockers.append("DETERMINISTIC_ITEM_NOT_COVERED")
    if unclassified:
        blockers.append("UNCLASSIFIED_ITEM")
    # Human debt is withheld until the automated evidence is current and passing.
    surfaced = [] if blockers else human_items
    status = "BLOCKED" if blockers else "HUMAN_ATTENTION_REQUIRED" if surfaced else "CLEAR"
    return {
        "schema_version": 3,
        "status": status,
        "build_commit_sha": evidence.build.commit_sha if evidence is not None else None,
        "current_commit_sha": current_commit_sha,
        "scenario_id": evidence.scenario_id if evidence is not None else None,
        "blocking_reasons": blockers,
        "human_attention_required": bool(surfaced),
        "automation_attention_required": bool(blockers),
        "item_count": len(surfaced),
        "categories": sorted({str(i["category"]) for i in surfaced}),
        "items": [i["description"] for i in surfaced],
        "categorized_items": surfaced,
        "deferred_human_item_count": len(human_items) - len(surfaced),
        "excluded_automated_items": [i for i in deterministic if i["covered_by_automation"]],
        "automation_debt_items": automation_debt,
        "unclassified_items": unclassified,
    }
