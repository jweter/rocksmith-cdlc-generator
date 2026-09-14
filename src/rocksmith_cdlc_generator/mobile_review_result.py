"""Local/private human review-result records for mobile Product Reality.

This module records an explicit human PASS/FAIL/FLAG against the exact
repository-safe mobile evidence identity.  It never derives a human verdict
and never treats mobile review as Windows/Rocksmith gameplay acceptance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .score_source import ArrangementRole

_SCHEMA_VERSION = 1
_ALLOWED_RESULTS = {"PASS", "FAIL", "FLAG"}


@dataclass(frozen=True)
class MobileReviewResult:
    schema_version: int
    commit: str
    scenario: str
    scenario_sha256: str
    arrangement: str
    project_recording_sha256: str
    tempo_map_sha256: str
    result: str
    reviewed_at_utc: str
    notes: str
    desktop_product_reality_cleared: bool
    identity_sha256: str


def _required_text(value: object, name: str) -> str:
    text = str(value).strip()
    if not text or text.upper() == "UNKNOWN":
        raise ValueError(f"{name} must be present and authoritative")
    return text


def _require_hex_digest(value: object, name: str, length: int) -> str:
    text = _required_text(value, name).lower()
    if len(text) != length or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{name} must be a {length}-character hexadecimal digest")
    return text


def _normalize_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("reviewed_at_utc must include a timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _identity_payload(
    *,
    commit: str,
    scenario: str,
    scenario_sha256: str,
    arrangement: str,
    project_recording_sha256: str,
    tempo_map_sha256: str,
) -> dict[str, str]:
    return {
        "commit": commit,
        "scenario": scenario,
        "scenario_sha256": scenario_sha256,
        "arrangement": arrangement,
        "project_recording_sha256": project_recording_sha256,
        "tempo_map_sha256": tempo_map_sha256,
    }


def _identity_sha256(payload: Mapping[str, str]) -> str:
    canonical = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def build_mobile_review_result(
    report: Mapping[str, Any],
    *,
    arrangement: ArrangementRole,
    result: str,
    notes: str = "",
    reviewed_at_utc: str | None = None,
) -> MobileReviewResult:
    """Bind an explicit human verdict to the exact sanitized evidence identity."""
    normalized_result = result.strip().upper()
    if normalized_result not in _ALLOWED_RESULTS:
        raise ValueError("result must be PASS, FAIL, or FLAG")

    commit = _require_hex_digest(report.get("commit"), "commit", 40)
    scenario = _required_text(report.get("scenario"), "scenario")
    scenario_sha256 = _require_hex_digest(report.get("scenario_sha256"), "scenario_sha256", 64)
    project_recording_sha256 = _require_hex_digest(
        report.get("project_recording_sha256"), "project_recording_sha256", 64
    )
    tempo_map_sha256 = _require_hex_digest(report.get("tempo_map_sha256"), "tempo_map_sha256", 64)
    arrangement_name = arrangement.value

    identity = _identity_payload(
        commit=commit,
        scenario=scenario,
        scenario_sha256=scenario_sha256,
        arrangement=arrangement_name,
        project_recording_sha256=project_recording_sha256,
        tempo_map_sha256=tempo_map_sha256,
    )
    return MobileReviewResult(
        schema_version=_SCHEMA_VERSION,
        commit=commit,
        scenario=scenario,
        scenario_sha256=scenario_sha256,
        arrangement=arrangement_name,
        project_recording_sha256=project_recording_sha256,
        tempo_map_sha256=tempo_map_sha256,
        result=normalized_result,
        reviewed_at_utc=_normalize_timestamp(reviewed_at_utc),
        notes=notes,
        desktop_product_reality_cleared=False,
        identity_sha256=_identity_sha256(identity),
    )


def _validate_record(raw: Mapping[str, Any]) -> MobileReviewResult:
    if raw.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported mobile review result schema_version")
    if raw.get("desktop_product_reality_cleared") is not False:
        raise ValueError("mobile review cannot clear desktop Product Reality")

    try:
        arrangement = ArrangementRole(str(raw["arrangement"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid arrangement in mobile review result") from exc

    report = {
        "commit": raw.get("commit"),
        "scenario": raw.get("scenario"),
        "scenario_sha256": raw.get("scenario_sha256"),
        "project_recording_sha256": raw.get("project_recording_sha256"),
        "tempo_map_sha256": raw.get("tempo_map_sha256"),
    }
    rebuilt = build_mobile_review_result(
        report,
        arrangement=arrangement,
        result=str(raw.get("result", "")),
        notes=str(raw.get("notes", "")),
        reviewed_at_utc=str(raw.get("reviewed_at_utc", "")),
    )
    if raw.get("identity_sha256") != rebuilt.identity_sha256:
        raise ValueError("mobile review result identity digest mismatch")
    return rebuilt


def read_mobile_review_results(history_path: Path) -> list[MobileReviewResult]:
    """Read and validate append-only local review history."""
    if not history_path.exists():
        return []
    records: list[MobileReviewResult] = []
    for line_number, line in enumerate(history_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid mobile review history JSON on line {line_number}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"mobile review history line {line_number} must be an object")
        records.append(_validate_record(raw))
    return records


def append_mobile_review_result(history_path: Path, record: MobileReviewResult) -> None:
    """Append one validated record without overwriting earlier human evidence."""
    _validate_record(asdict(record))
    read_mobile_review_results(history_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(asdict(record), sort_keys=True, separators=(",", ":")) + "\n")
