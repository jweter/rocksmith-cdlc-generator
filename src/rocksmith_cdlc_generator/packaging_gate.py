from __future__ import annotations

from pathlib import Path

from .validation import ValidationReport, validate_project


class PackagingBlockedError(RuntimeError):
    """Raised when a downstream export/build is attempted on a failing project."""


def require_packaging_ready(project_dir: Path) -> ValidationReport:
    """Return current validation state or block downstream packaging on FAIL."""
    report = validate_project(project_dir)
    if not report.can_package:
        codes = [item.code for item in report.review_queue if item.severity == "FAIL"]
        detail = ", ".join(codes[:8]) or "validation_failed"
        raise PackagingBlockedError(
            f"Project validation is FAIL; packaging is blocked ({detail}). Run `cdlc validate` and resolve hard failures first."
        )
    return report
