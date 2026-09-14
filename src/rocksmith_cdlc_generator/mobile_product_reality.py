"""Privacy-safe mobile Product Reality evidence rendering.

The renderer deliberately consumes derived evidence only. It does not read audio,
score, workspace, DLC, or Rocksmith installation data.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .mobile_timeline import build_mobile_timeline_landmarks
from .mobile_timing_phase import beat_phase_delta
from .score_source import ArrangementRole

if TYPE_CHECKING:
    from .beats import TempoMap
    from .private_product_reality import PrivateProductRealityEvidence, ProductRealityCheck

_ALLOWED_RESULTS = {"PASS", "FAIL", "FLAG", "UNREVIEWED"}
_ALLOWED_AUTOMATED_RESULTS = {"PASS", "FAIL", "REVIEW_REQUIRED", "UNKNOWN"}


def render_mobile_review(report: Mapping[str, Any]) -> str:
    """Render a self-contained, responsive iPhone review artifact."""
    commit = _required(report, "commit")
    scenario = _required(report, "scenario")
    scenario_sha256 = str(report.get("scenario_sha256", "UNKNOWN"))
    observed_at_utc = str(report.get("observed_at_utc", "UNKNOWN"))
    project_recording_sha256 = str(report.get("project_recording_sha256", "UNKNOWN"))
    tempo_map_sha256 = str(report.get("tempo_map_sha256", "UNKNOWN"))
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

    landmarks = report.get("timeline_landmarks", [])
    if not isinstance(landmarks, Sequence) or isinstance(landmarks, (str, bytes)):
        raise ValueError("timeline_landmarks must be a sequence")
    landmark_rows = "".join(_timeline_landmark_row(item) for item in landmarks)
    timeline_html = (
        f'<section class="card"><h2>Timeline landmarks</h2><table>'
        f"<tr><th>Time</th><th>Arrangement</th><th>Landmark</th></tr>{landmark_rows}</table></section>"
        if landmark_rows
        else '<section class="card"><h2>Timeline landmarks</h2><p>No sanitized landmarks were supplied.</p></section>'
    )

    eof_differential = report.get("eof_differential")
    eof_differential_html = (
        _eof_differential_card(eof_differential)
        if eof_differential is not None
        else (
            '<section class="card"><h2>EOF timing differential</h2>'
            '<p>No current sanitized EOF differential was supplied.</p></section>'
        )
    )

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
<div class=\"meta\"><strong>Measured at:</strong> {escape(observed_at_utc)}</div>
<div class=\"meta\"><strong>Recording hash:</strong> {escape(project_recording_sha256)}</div>
<div class=\"meta\"><strong>Tempo map hash:</strong> {escape(tempo_map_sha256)}</div>
<div class=\"result\">Human review: {escape(result)}</div></section>
<section class=\"card\"><h2>Automated result: {escape(automated_result)}</h2>{failed_checks_html}</section>
{timeline_html}
{eof_differential_html}
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


def _timeline_landmark_row(item: Any) -> str:
    if not isinstance(item, Mapping):
        raise ValueError("each timeline landmark must be a mapping")
    landmark_id = _required(item, "id")
    arrangement = _required(item, "arrangement").capitalize()
    seconds = item.get("seconds", "UNKNOWN")
    return (
        f"<tr><td>{escape(str(seconds))} s</td>"
        f"<td>{escape(arrangement)}</td><td>{escape(landmark_id)}</td></tr>"
    )


def _eof_differential_card(item: Any) -> str:
    if not isinstance(item, Mapping):
        raise ValueError("eof_differential must be a mapping")
    arrangement = _required(item, "arrangement").capitalize()
    classification = _required(item, "classification")
    first = item.get("first_playable_delta_seconds", "UNKNOWN")
    median_error = item.get("median_abs_error_seconds", "UNKNOWN")
    max_error = item.get("max_abs_error_seconds", "UNKNOWN")
    spread = item.get("delta_spread_seconds", "UNKNOWN")
    tolerance = item.get("timing_tolerance_seconds", "UNKNOWN")
    matched = item.get("matched", "UNKNOWN")
    return (
        '<section class="card"><h2>EOF timing differential</h2><table>'
        f"<tr><th>Arrangement</th><td>{escape(arrangement)}</td></tr>"
        f"<tr><th>Classification</th><td>{escape(classification)}</td></tr>"
        f"<tr><th>First-playable delta</th><td>{escape(str(first))} s</td></tr>"
        f"<tr><th>Median absolute error</th><td>{escape(str(median_error))} s</td></tr>"
        f"<tr><th>Maximum absolute error</th><td>{escape(str(max_error))} s</td></tr>"
        f"<tr><th>Delta spread</th><td>{escape(str(spread))} s</td></tr>"
        f"<tr><th>Timing tolerance</th><td>{escape(str(tolerance))} s</td></tr>"
        f"<tr><th>Within tolerance</th><td>{escape(str(matched))}</td></tr>"
        "</table></section>"
    )


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
_COLLECTION_ERROR_PREFIX = "collection_"
_SANITIZED_COLLECTION_MESSAGE = (
    "Automated evidence collection reported an error for this scenario; "
    "see local Product Reality evidence for detail."
)
_RAW_MESSAGE_CODES = {"psarc_registration"}
_SANITIZED_RAW_MESSAGE = (
    "Automated registration re-verification reported drift for this scenario; "
    "see local Product Reality evidence for detail."
)


def _sanitized_check_message(check: "ProductRealityCheck") -> str:
    if check.code.startswith(_COLLECTION_ERROR_PREFIX):
        return _SANITIZED_COLLECTION_MESSAGE
    if check.code in _RAW_MESSAGE_CODES and check.status != "PASS":
        return _SANITIZED_RAW_MESSAGE
    return check.message


def build_mobile_review_report(
    evidence: "PrivateProductRealityEvidence",
    *,
    tempo_map: "TempoMap | None" = None,
    tempo_map_sha256: str | None = None,
    eof_differential: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map deterministic Product Reality evidence onto the mobile review contract."""
    checks_by_code: dict[str, "ProductRealityCheck"] = {check.code: check for check in evidence.checks}
    checkpoints_by_role: dict[Any, list[Any]] = {}
    for checkpoint in evidence.checkpoint_observations:
        checkpoints_by_role.setdefault(checkpoint.role, []).append(checkpoint)
    role_observation_by_name = {ro.role.value: ro for ro in evidence.role_observations}

    requested_role_names = [
        code[: -len(_FIRST_EVENT_SUFFIX)]
        for code in checks_by_code
        if code.endswith(_FIRST_EVENT_SUFFIX) and code[: -len(_FIRST_EVENT_SUFFIX)] in _ROLE_NAMES
    ]

    arrangements: list[dict[str, Any]] = []
    for role_name in requested_role_names:
        role_observation = role_observation_by_name.get(role_name)
        first_playable: Any = "UNKNOWN"
        phase_beats: Any = "UNKNOWN"
        drift_seconds: Any = "UNKNOWN"
        first_event_check = checks_by_code.get(f"{role_name}{_FIRST_EVENT_SUFFIX}")
        if role_observation is not None:
            first_playable = role_observation.first_playable_seconds

            if (
                tempo_map is not None
                and tempo_map_sha256 is not None
                and evidence.tempo_map_sha256 is not None
                and tempo_map_sha256 == evidence.tempo_map_sha256
                and first_event_check is not None
                and isinstance(first_event_check.observed, (int, float))
                and isinstance(first_event_check.expected, (int, float))
            ):
                try:
                    phase_beats = beat_phase_delta(
                        tempo_map,
                        observed_seconds=float(first_event_check.observed),
                        expected_seconds=float(first_event_check.expected),
                    )
                except ValueError:
                    phase_beats = "UNKNOWN"

            baseline_error: float | None = None
            if (
                first_event_check is not None
                and isinstance(first_event_check.observed, (int, float))
                and isinstance(first_event_check.expected, (int, float))
            ):
                baseline_error = first_event_check.observed - first_event_check.expected

            drift_measurements: list[tuple[str, float]] = []
            if baseline_error is not None:
                for checkpoint in checkpoints_by_role.get(role_observation.role, []):
                    checkpoint_error = checkpoint.observed_audio_seconds - checkpoint.expected_audio_seconds
                    drift_measurements.append((checkpoint.checkpoint_id, checkpoint_error - baseline_error))
            if len(drift_measurements) == 1:
                drift_seconds = drift_measurements[0][1]
            elif len(drift_measurements) > 1:
                worst_id, worst_value = max(drift_measurements, key=lambda item: abs(item[1]))
                drift_seconds = f"{worst_value:+.3f} (worst of {len(drift_measurements)}, checkpoint '{worst_id}')"

        arrangements.append(
            {
                "name": role_name.capitalize(),
                "first_playable_seconds": first_playable,
                "phase_beats": phase_beats,
                "drift_seconds": drift_seconds,
            }
        )

    failed_checks = [
        {"code": check.code, "status": check.status, "message": _sanitized_check_message(check)}
        for check in evidence.checks
        if check.status != "PASS"
    ]

    return {
        "commit": evidence.build.commit_sha or "unknown-build",
        "scenario": evidence.scenario_id,
        "scenario_sha256": evidence.scenario_sha256,
        "observed_at_utc": evidence.observed_at_utc,
        "project_recording_sha256": evidence.project_recording_sha256 or "UNKNOWN",
        "tempo_map_sha256": evidence.tempo_map_sha256 or "UNKNOWN",
        "automated_result": evidence.result,
        "failed_checks": failed_checks,
        "timeline_landmarks": build_mobile_timeline_landmarks(evidence),
        "eof_differential": None if eof_differential is None else dict(eof_differential),
        "arrangements": arrangements,
        "desktop_acceptance_debt": list(evidence.human_only_acceptance),
    }
