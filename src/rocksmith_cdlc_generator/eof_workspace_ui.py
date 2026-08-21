from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from .eof_bridge import (
    EOFBridgeError,
    discover_eof_executable,
    launch_project_score_in_eof,
    resolve_registered_score_for_eof,
)
from .eof_hand_position_project import load_current_project_eof_hand_position_status
from .eof_project_report import load_current_project_eof_compatibility_report


@dataclass(frozen=True)
class EOFWorkspaceStatus:
    available: bool
    button_text: str
    status_text: str
    executable: Path | None = None
    score_path: Path | None = None


@dataclass(frozen=True)
class EOFReportWorkspaceStatus:
    current: bool
    status_text: str


@dataclass(frozen=True)
class EOFHandPositionWorkspaceStatus:
    current: bool
    status_text: str


def build_eof_workspace_status(project_dir: Path) -> EOFWorkspaceStatus:
    """Describe whether the current project can be opened in user-installed EOF.

    This is read-only capability detection. It never installs EOF, changes project
    authority, or records a human review decision.
    """

    try:
        score_path = resolve_registered_score_for_eof(project_dir)
    except (EOFBridgeError, FileNotFoundError, ValueError) as exc:
        return EOFWorkspaceStatus(
            available=False,
            button_text="Open in EOF",
            status_text=f"EOF reference unavailable: {exc}",
        )

    executable = discover_eof_executable()
    if executable is None:
        return EOFWorkspaceStatus(
            available=False,
            button_text="Open in EOF",
            status_text=(
                "Compatible Guitar Pro score is ready for EOF reference review, but Editor on Fire "
                "was not found. Set ROCKSMITH_CDLC_EOF_EXE or place eof.exe on PATH."
            ),
            score_path=score_path,
        )

    return EOFWorkspaceStatus(
        available=True,
        button_text="Open in EOF",
        status_text=(
            f"Optional reference: {score_path.name} · EOF {executable.name}. "
            "Opening EOF does not change project authority."
        ),
        executable=executable,
        score_path=score_path,
    )


def build_eof_report_workspace_status(project_dir: Path) -> EOFReportWorkspaceStatus:
    """Summarize the latest current EOF discrepancy report without granting authority."""

    try:
        report = load_current_project_eof_compatibility_report(project_dir)
    except (EOFBridgeError, FileNotFoundError, ValueError) as exc:
        return EOFReportWorkspaceStatus(
            current=False,
            status_text=f"EOF comparison report is stale or unavailable: {exc}",
        )

    if report is None:
        return EOFReportWorkspaceStatus(
            current=False,
            status_text=(
                "No current EOF comparison report. Source-bound EOF observations remain optional "
                "advisory evidence."
            ),
        )

    mismatch_count = len(report.comparison.mismatches)
    evidence = f"EOF evidence {report.eof_version} · fixture {report.comparison.fixture_id}"
    if mismatch_count == 0:
        return EOFReportWorkspaceStatus(
            current=True,
            status_text=(
                f"Current EOF comparison: 0 discrepancies for {report.instrument.title()} · {evidence}. "
                "Advisory only; this does not accept chart state."
            ),
        )

    counts = Counter(item.field for item in report.comparison.mismatches)
    detail = ", ".join(
        f"{field.replace('_', ' ')}: {count}" for field, count in sorted(counts.items())
    )
    discrepancy_word = "discrepancy" if mismatch_count == 1 else "discrepancies"
    return EOFReportWorkspaceStatus(
        current=True,
        status_text=(
            f"Current EOF comparison: {mismatch_count} {discrepancy_word} for "
            f"{report.instrument.title()} ({detail}) · {evidence}. Review evidence only."
        ),
    )


def build_eof_hand_position_workspace_status(
    project_dir: Path,
) -> EOFHandPositionWorkspaceStatus:
    """Summarize current EOF hand-position evidence without granting fingering authority."""

    try:
        status = load_current_project_eof_hand_position_status(project_dir)
    except (EOFBridgeError, FileNotFoundError, ValueError) as exc:
        return EOFHandPositionWorkspaceStatus(
            current=False,
            status_text=f"EOF hand-position evidence is stale or unavailable: {exc}",
        )

    if status is None:
        return EOFHandPositionWorkspaceStatus(
            current=False,
            status_text=(
                "No current EOF hand-position evidence. Observed fret-hand-position markers are "
                "optional advisory evidence and do not define preferred fingering."
            ),
        )

    marker_count = status.evidence.observation_count
    marker_word = "marker" if marker_count == 1 else "markers"
    return EOFHandPositionWorkspaceStatus(
        current=True,
        status_text=(
            f"Current EOF hand-position evidence: {marker_count} {marker_word} for "
            f"{status.instrument.title()} · EOF {status.eof_version} · fixture "
            f"{status.evidence.fixture_id}. Advisory only; this does not accept fingering or playability."
        ),
    )


class EOFWorkspaceMixin:
    """Expose the optional Editor on Fire reference bridge in Song Workspace."""

    def _build_timeline(self) -> None:
        super()._build_timeline()

        box = ttk.LabelFrame(self.timeline_tab, text="Editor on Fire reference", padding=8)
        box.pack(fill="x", pady=(6, 0))

        launch_row = ttk.Frame(box)
        launch_row.pack(fill="x")
        self.eof_status_label = ttk.Label(
            launch_row,
            text="Checking optional EOF integration…",
            wraplength=850,
            justify="left",
        )
        self.eof_status_label.pack(side="left", fill="x", expand=True)
        self.eof_open_button = ttk.Button(
            launch_row,
            text="Open in EOF",
            command=self._open_project_in_eof,
            state="disabled",
        )
        self.eof_open_button.pack(side="right", padx=(12, 0))

        self.eof_report_status_label = ttk.Label(
            box,
            text="Checking EOF comparison evidence…",
            wraplength=850,
            justify="left",
        )
        self.eof_report_status_label.pack(fill="x", pady=(6, 0))
        self.eof_hand_position_status_label = ttk.Label(
            box,
            text="Checking EOF hand-position evidence…",
            wraplength=850,
            justify="left",
        )
        self.eof_hand_position_status_label.pack(fill="x", pady=(6, 0))
        self.after_idle(self._refresh_eof_workspace_status)

    def refresh(self) -> None:
        super().refresh()
        self._refresh_eof_workspace_status()

    def _refresh_eof_workspace_status(self) -> None:
        if not hasattr(self, "eof_status_label"):
            return
        status = build_eof_workspace_status(self.project)
        self.eof_status_label.configure(text=status.status_text)
        self.eof_open_button.configure(
            text=status.button_text,
            state="normal" if status.available else "disabled",
        )
        if hasattr(self, "eof_report_status_label"):
            report_status = build_eof_report_workspace_status(self.project)
            self.eof_report_status_label.configure(text=report_status.status_text)
        if hasattr(self, "eof_hand_position_status_label"):
            hand_position_status = build_eof_hand_position_workspace_status(self.project)
            self.eof_hand_position_status_label.configure(text=hand_position_status.status_text)

    def _open_project_in_eof(self) -> None:
        try:
            launch_project_score_in_eof(self.project)
        except (EOFBridgeError, FileNotFoundError, ValueError, OSError) as exc:
            messagebox.showerror("Editor on Fire", str(exc), parent=self)
            self._refresh_eof_workspace_status()
            return

        self.eof_status_label.configure(
            text=(
                "Opened the registered Guitar Pro score in EOF as an external reference. "
                "EOF edits are not imported or accepted automatically."
            )
        )
