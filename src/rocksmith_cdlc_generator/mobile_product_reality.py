"""Privacy-safe mobile Product Reality evidence rendering.

The renderer deliberately consumes derived evidence only. It does not read audio,
score, workspace, DLC, or Rocksmith installation data.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .score_source import ArrangementRole

if TYPE_CHECKING:
    from .private_product_reality import PrivateProductRealityEvidence, ProductRealityCheck

_ALLOWED_RESULTS = {"PASS", "FAIL", "FLAG", "UNREVIEWED"}
_ALLOWED_AUTOMATED_RESULTS = {"PASS", "FAIL", "REVIEW_REQUIRED", "UNKNOWN"}


def render_mobile_review(report: Mapping[str, Any]) -> str:
    """Render a self-contained, responsive iPhone review artifact.

    Required report fields bind the review to an exact build and scenario. The
    artifact is intentionally read-only: human review is recorded separately so
    opening HTML cannot mutate authoritative Product Reality state.
    """
    commit = _required(report, "commit")
    scenario = _required(report, "scenario")
    scenario_sha256 = str(report.get("scenario_sha256", "UNKNOWN"))
    result = str(report.get("human_result", "UNREVIEWED")).upper()
    if result not in _ALLOWED_RESULTS:
        raise ValueError(f"unsupported human_result: {result}")

    automated_result = str(report.get("automated_result", "UNKNOWN")).upper()
    if automated_result not in _ALLOWED_AUTOMATED_RESULTS:
        raise ValueError(f"unsupported automated_result: {automated_result}")
    failed_checks = report.get("failed_checks", [])
    if not isinstance(failed_checks, Sequence) or isinstance(failed_checks, (str, bytes)):
        raise ValueError("failed_checks must be a sequence")
    failed_check_items = "".join(_failed_check_item(item) for item in failed_checks)
    if failed_check_items:
        failed_checks_html = f"<ul>{failed_check_items}</ul>"
    elif automated_result == "PASS":
        failed_checks_html = "<p>All deterministic checks passed.</p>"
    else:
        failed_checks_html = "<p>No deterministic check results were supplied.</p>"

    arrangements = report.get("arrangements", [])
    if not isinstance(arrangements, Sequence) or isinstance(arrangements, (str, bytes)):
        raise ValueError("arrangements must be a sequence")

    cards = "".join(_arrangement_card(item) for item in arrangements)
    debt = report.get("desktop_acceptance_debt", [])
    if not isinstance(debt, Sequence) or isinstance(debt, (str, bytes)):
        raise ValueError("desktop_acceptance_debt must be a sequence")
    debt_items = "".join(f"<li>{escape(str(item))}</li>" for item in debt)

    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">
<title>Rocksmith Mobile Review</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;margin:0;padding:16px;line-height:1.4;background:#f5f5f7;color:#1d1d1f}}
main{{max-width:760px;margin:auto}} .card{{background:white;border-radius:14px;padding:14px;margin:12px 0;box-shadow:0 1px 4px #0002}}
.meta{{overflow-wrap:anywhere;font-family:ui-monospace,monospace;font-size:.86rem}} table{{width:100%;border-collapse:collapse}}
th,td{{padding:8px 4px;border-bottom:1px solid #ddd;text-align:left}} .result{{font-weight:700;font-size:1.1rem}}
</style></head><body><main>
<h1>Rocksmith Mobile Review</h1>
<section class=\"card\"><div><strong>Scenario:</strong> {escape(scenario)}</div>
<div class=\"meta\"><strong>Commit:</strong> {escape(commit)}</div>
<div class=\"meta\"><strong>Scenario hash:</strong> {escape(scenario_sha256)}</div>
<div class=\"result\">Human review: {escape(result)}</div></section>
<section class=\"card\"><h2>Automated result: {escape(automated_result)}</h2>{failed_checks_html}</section>
{cards}
<section class=\"card\"><h2>Desktop-only acceptance debt</h2><ul>{debt_items}</ul>
<p>This mobile artifact does not verify packaging, PSARC integration, Rocksmith playback, tones, or gameplay.</p></section>
</main></body></html>"""


def _failed_check_item(item: Any) -> str:
    if not isinstance(item, Mapping):
        raise ValueError("each failed check must be a mapping")
    code = _required(item, "code")
    status = str(item.get("status", "UNKNOWN")).upper()
    message = str(item.get("message", ""))
    return f"<li><strong>{escape(status)}</strong> {escape(code)}: {escape(message)}</li>"


def _arrangement_card(item: Any) -> str:
    if not isinstance(item, Mapping):
        raise ValueError("each arrangement must be a mapping")
    name = _required(item, "name")
    first = item.get("first_playable_seconds", "UNKNOWN")
    phase = item.get("phase_beats", "UNKNOWN")
    drift = item.get("drift_seconds", "UNKNOWN")
    return (
        '<section class="card">'
        f"<h2>{escape(name)}</h2><table>"
        f"<tr><th>First playable</th><td>{escape(str(first))} s</td></tr>"
        f"<tr><th>Beat phase</th><td>{escape(str(phase))} beats</td></tr>"
        f"<tr><th>Measured drift</th><td>{escape(str(drift))} s</td></tr>"
        "</table></section>"
    )


def _required(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required field: {key}")
    return value.strip()


_FIRST_EVENT_SUFFIX = "_first_event"
_ROLE_NAMES = {role.value for role in ArrangementRole}


def build_mobile_review_report(evidence: "PrivateProductRealityEvidence") -> dict[str, Any]:
    """Map deterministic Private Product Reality evidence onto the mobile review contract.

    This reuses the already-evaluated `evidence.checks` deltas instead of recomputing timing
    math, so the mobile artifact cannot disagree with the authoritative shared-timing result it
    presents. Beat-space phase is left `UNKNOWN`: the evidence model only carries seconds, and
    mislabeling a seconds value as beats would misstate musical position (see #569/#455 -
    constant phase displacement must stay distinguishable from cumulative drift, not be guessed).
    """
    checks_by_code: dict[str, "ProductRealityCheck"] = {check.code: check for check in evidence.checks}
    checkpoints_by_role: dict[Any, list[Any]] = {}
    for checkpoint in evidence.checkpoint_observations:
        checkpoints_by_role.setdefault(checkpoint.role, []).append(checkpoint)
    role_observation_by_name = {ro.role.value: ro for ro in evidence.role_observations}

    # evaluate_shared_timing_observation() emits one `{role}_first_event` check per requested
    # scenario role, even when that role's observation failed to collect, so this is the
    # authoritative requested-role list -- deriving cards from role_observations alone would
    # silently drop the card for any role whose collection failed. Checks are also restricted to
    # known ArrangementRole values: a checkpoint whose free-form `id` happens to end in
    # `_first_event` (e.g. a checkpoint id of "chorus_first_event") would otherwise produce its
    # own `checkpoint_chorus_first_event` check code, which also matches the suffix test and
    # would fabricate a phantom "Checkpoint_chorus" arrangement card.
    requested_role_names = [
        code[: -len(_FIRST_EVENT_SUFFIX)]
        for code in checks_by_code
        if code.endswith(_FIRST_EVENT_SUFFIX) and code[: -len(_FIRST_EVENT_SUFFIX)] in _ROLE_NAMES
    ]

    arrangements: list[dict[str, Any]] = []
    for role_name in requested_role_names:
        role_observation = role_observation_by_name.get(role_name)
        first_playable: Any = "UNKNOWN"
        drift_seconds: Any = "UNKNOWN"
        if role_observation is not None:
            first_playable = role_observation.first_playable_seconds
            drift_measurements: list[tuple[str, float]] = []
            for checkpoint in checkpoints_by_role.get(role_observation.role, []):
                drift_check = checks_by_code.get(f"checkpoint_{checkpoint.checkpoint_id}_drift")
                if drift_check is not None and isinstance(drift_check.observed, (int, float)):
                    drift_measurements.append((checkpoint.checkpoint_id, drift_check.observed))
            if len(drift_measurements) == 1:
                drift_seconds = drift_measurements[0][1]
            elif len(drift_measurements) > 1:
                worst_id, worst_value = max(drift_measurements, key=lambda item: abs(item[1]))
                drift_seconds = f"{worst_value:+.3f} (worst of {len(drift_measurements)}, checkpoint '{worst_id}')"

        arrangements.append(
            {
                "name": role_name.capitalize(),
                "first_playable_seconds": first_playable,
                "phase_beats": "UNKNOWN",
                "drift_seconds": drift_seconds,
            }
        )

    failed_checks = [
        {"code": check.code, "status": check.status, "message": check.message}
        for check in evidence.checks
        if check.status != "PASS"
    ]

    return {
        "commit": evidence.build.commit_sha or "unknown-build",
        "scenario": evidence.scenario_id,
        "scenario_sha256": evidence.scenario_sha256,
        "automated_result": evidence.result,
        "failed_checks": failed_checks,
        "arrangements": arrangements,
        "desktop_acceptance_debt": list(evidence.human_only_acceptance),
    }
