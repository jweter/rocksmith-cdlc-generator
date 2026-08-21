from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from .eof_bridge import (
    EOFBridgeError,
    discover_eof_executable,
    launch_project_score_in_eof,
    resolve_registered_score_for_eof,
)


@dataclass(frozen=True)
class EOFWorkspaceStatus:
    available: bool
    button_text: str
    status_text: str
    executable: Path | None = None
    score_path: Path | None = None


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


class EOFWorkspaceMixin:
    """Expose the optional Editor on Fire reference bridge in Song Workspace."""

    def _build_timeline(self) -> None:
        super()._build_timeline()

        box = ttk.LabelFrame(self.timeline_tab, text="Editor on Fire reference", padding=8)
        box.pack(fill="x", pady=(6, 0))

        self.eof_status_label = ttk.Label(
            box,
            text="Checking optional EOF integration…",
            wraplength=850,
            justify="left",
        )
        self.eof_status_label.pack(side="left", fill="x", expand=True)
        self.eof_open_button = ttk.Button(
            box,
            text="Open in EOF",
            command=self._open_project_in_eof,
            state="disabled",
        )
        self.eof_open_button.pack(side="right", padx=(12, 0))
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
