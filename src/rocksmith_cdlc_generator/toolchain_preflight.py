"""Toolchain preflight that reports BLOCKED, never a misleading pass (#796 slice 52).

Packaging needs external tools (for example Wwise or a PSARC bridge). If any required
tool is missing the run must say so as blocked evidence; it must never look like a pass.
The tool lookup is injected (``which``), so the check is pure and testable; production
passes ``shutil.which``.

``READY`` only when at least one tool is declared and every declared tool resolved. An
empty requirement list is ``BLOCKED`` (``NO_TOOLS_DECLARED``) so a forgotten declaration
cannot pass vacuously. An invalid tool name is ``BLOCKED`` (``INVALID_TOOL_NAME``). A
lookup that raises or returns a non-path value counts as missing (fail closed).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

ToolchainStatus = Literal["READY", "BLOCKED"]
ToolchainReason = Literal["", "NO_TOOLS_DECLARED", "INVALID_TOOL_NAME", "MISSING_TOOLS"]


class ToolchainPreflightResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ToolchainStatus
    reason: ToolchainReason = ""
    resolved: tuple[tuple[str, str], ...] = ()
    missing: tuple[str, ...] = ()
    blocked_evidence: str = ""


def _blocked(
    reason: ToolchainReason,
    evidence: str,
    *,
    missing: tuple[str, ...] = (),
    resolved: tuple[tuple[str, str], ...] = (),
) -> ToolchainPreflightResult:
    return ToolchainPreflightResult(
        status="BLOCKED",
        reason=reason,
        missing=missing,
        resolved=resolved,
        blocked_evidence=evidence,
    )


def run_toolchain_preflight(
    required: Iterable[object],
    which: Callable[[str], str | None],
) -> ToolchainPreflightResult:
    """Resolve every required tool through ``which``; ``READY`` only if all resolve."""

    names: list[object] = list(required)
    if not names:
        return _blocked("NO_TOOLS_DECLARED", "No required tools were declared for this check.")

    unique: list[str] = []
    for name in names:
        if not isinstance(name, str) or not name or name != name.strip() or " " in name:
            return _blocked("INVALID_TOOL_NAME", f"Invalid tool name: {name!r}")
        if name not in unique:
            unique.append(name)

    resolved: list[tuple[str, str]] = []
    missing: list[str] = []
    for name in unique:
        try:
            found = which(name)
        except Exception:  # noqa: BLE001 - a failing lookup must read as missing
            found = None
        if isinstance(found, str) and found.strip():
            resolved.append((name, found))
        else:
            missing.append(name)

    if missing:
        ordered = tuple(sorted(missing))
        return _blocked(
            "MISSING_TOOLS",
            "Required tool(s) not found: " + ", ".join(ordered),
            missing=ordered,
            resolved=tuple(resolved),
        )
    return ToolchainPreflightResult(status="READY", resolved=tuple(resolved))
