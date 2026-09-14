"""Privacy-safe mobile Product Reality evidence rendering.

The renderer deliberately consumes derived evidence only. It does not read audio,
score, workspace, DLC, or Rocksmith installation data.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Any, Mapping, Sequence

if TYPE_CHECKING:
    from .private_product_reality import PrivateProductRealityEvidence, ProductRealityCheck

_ALLOWED_RESULTS = {"PASS", "FAIL", "FLAG", "UNREVIEWED"}


def render_mobile_review(report: Mapping[str, Any]) -> str:
    """Render a self-contained, responsive iPhone review artifact.

    Required report fields bind the review to an exact build and scenario. The
    artifact is intentionally read-only: human review is recorded separately so
    opening HTML cannot mutate authoritative Product Reality state.
    """
    commit = _required(report, "commit")
    scenario = _required(report, "scenario")
    result = str(report.get("human_result", "UNREVIEWED")).upper()
    if result not in _ALLOWED_RESULTS:
        raise ValueError(f"unsupported human_result: {result}")

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
<div class=\"result\">Human review: {escape(result)}</div></section>
{cards}
<section class=\"card\"><h2>Desktop-only acceptance debt</h2><ul>{debt_items}</ul>
<p>This mobile artifact does not verify packaging, PSARC integration, Rocksmith playback, tones, or gameplay.</p></section>
</main></body></html>"""


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

    arrangements: list[dict[str, Any]] = []
    for role_observation in evidence.role_observations:
        role = role_observation.role
        drift_seconds: Any = "UNKNOWN"
        role_checkpoints = checkpoints_by_role.get(role)
        if role_checkpoints:
            last_checkpoint_id = role_checkpoints[-1].checkpoint_id
            drift_check = checks_by_code.get(f"checkpoint_{last_checkpoint_id}_drift")
            if drift_check is not None and isinstance(drift_check.observed, (int, float)):
                drift_seconds = drift_check.observed

        arrangements.append(
            {
                "name": role.value.capitalize(),
                "first_playable_seconds": role_observation.first_playable_seconds,
                "phase_beats": "UNKNOWN",
                "drift_seconds": drift_seconds,
            }
        )

    return {
        "commit": evidence.build.commit_sha or "unknown-build",
        "scenario": evidence.scenario_id,
        "arrangements": arrangements,
        "desktop_acceptance_debt": list(evidence.human_only_acceptance),
    }
