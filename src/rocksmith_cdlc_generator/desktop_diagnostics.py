from __future__ import annotations

import json
from datetime import datetime, timezone, tzinfo
from pathlib import Path

_DIAGNOSTIC_LOG_NAME = "desktop_diagnostics.jsonl"


def diagnostic_level(message: str) -> str:
    text = message.lstrip().lower()
    if text.startswith("traceback") or "failed:" in text or "error:" in text:
        return "ERROR"
    if text.startswith("warning:") or "cannot be promoted" in text or "review needed" in text:
        return "WARNING"
    return "INFO"


def format_diagnostic_line(message: str, *, timestamp: datetime | None = None) -> str:
    when = timestamp or datetime.now().astimezone()
    level = diagnostic_level(message)
    return f"[{when:%H:%M:%S}] {level:<7} {message.rstrip()}"


def persist_project_diagnostic(project: Path | None, message: str, *, timestamp: datetime | None = None) -> None:
    """Best-effort local diagnostic persistence; logging must never break authoring."""

    if project is None:
        return
    try:
        project = project.expanduser().resolve()
        review_dir = project / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        when = timestamp or datetime.now(timezone.utc)
        payload = {
            "schema_version": 1,
            "timestamp": when.astimezone(timezone.utc).isoformat(),
            "level": diagnostic_level(message),
            "message": message.rstrip(),
        }
        with (review_dir / _DIAGNOSTIC_LOG_NAME).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True) + "\n")
    except Exception:
        # Diagnostics are observational only and must never become workflow authority.
        return


def _local_clock(timestamp: object, *, local_timezone: tzinfo | None = None) -> str:
    try:
        parsed = datetime.fromisoformat(str(timestamp))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local = parsed.astimezone(local_timezone) if local_timezone is not None else parsed.astimezone()
    except (TypeError, ValueError, OSError, OverflowError):
        return "--:--:--"
    return f"{local:%H:%M:%S}"


def read_recent_project_diagnostics(
    project: Path | None,
    *,
    limit: int = 8,
    local_timezone: tzinfo | None = None,
) -> list[str]:
    if project is None or limit < 1:
        return []
    path = project.expanduser().resolve() / "review" / _DIAGNOSTIC_LOG_NAME
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    recent: list[str] = []
    for raw in lines[-limit:]:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        clock = _local_clock(payload.get("timestamp"), local_timezone=local_timezone)
        level = str(payload.get("level") or "INFO")
        message = str(payload.get("message") or "")
        recent.append(f"[{clock}] {level:<7} {message}")
    return recent
