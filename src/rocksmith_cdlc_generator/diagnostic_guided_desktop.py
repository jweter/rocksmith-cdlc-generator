from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .build_identity import window_title
from .desktop_app import APP_TITLE
from .desktop_diagnostics import (
    format_diagnostic_line,
    persist_project_diagnostic,
    read_recent_project_diagnostics,
)
from .desktop_polish import polish_widget_tree
from .desktop_theme import PALETTE, apply_desktop_theme
from .guided_desktop import GuidedDesktopApp
from .models import ProjectManifest
from .song_readiness import SongReadiness


def workflow_diagnostic_key(project: Path | None, headline: str, detail: str) -> str:
    project_identity = str(project.expanduser().resolve()) if project is not None else "<none>"
    return f"{project_identity}|{headline}|{detail}"


class LiveDiagnosticsGuidedDesktopApp(GuidedDesktopApp):
    """Guided product shell with always-visible Product Reality diagnostics."""

    def __init__(self) -> None:
        self._active_diagnostic_task = ""
        self._last_workflow_diagnostic = ""
        self._diagnostic_project_load_in_progress = False
        super().__init__()
        apply_desktop_theme(self)
        polish_widget_tree(self)
        self._build_next_required_marker()
        self.title(window_title())

    def _build_next_required_marker(self) -> None:
        """Place a non-color-only cue immediately beside the exact next-action button."""

        if not hasattr(self, "next_action_button"):
            return
        parent = self.next_action_button.master
        self.next_required_marker = ttk.Label(
            parent,
            text="NEXT REQUIRED ACTION  →",
            style="Status.ReviewRequired.TLabel",
        )
        self._sync_next_required_marker()

    def _sync_next_required_marker(self) -> None:
        marker = getattr(self, "next_required_marker", None)
        if marker is None:
            return
        if self._guided_action_route is None:
            marker.pack_forget()
            return
        if not marker.winfo_manager():
            marker.pack(side="right", padx=(12, 0))

    def _update_guided_action(self, readiness: SongReadiness) -> None:
        super()._update_guided_action(readiness)
        self._sync_next_required_marker()

    def _build_layout(self) -> None:
        super()._build_layout()
        children = self.winfo_children()
        before = children[-1] if children else None
        frame = ttk.LabelFrame(self, text="Live diagnostics", padding=8)
        options = {"fill": "x", "padx": 12, "pady": (0, 8)}
        if before is not None:
            options["before"] = before
        frame.pack(**options)

        header = ttk.Frame(frame, style="Surface.TFrame")
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Testing view — recent operational events only; no audio or score contents are logged.",
            style="Surface.TLabel",
        ).pack(side="left")
        ttk.Button(header, text="Open full Activity Log", command=self._show_full_activity_log).pack(side="right")

        self.live_diagnostics_text = tk.Text(
            frame,
            height=5,
            wrap="word",
            state="disabled",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=8,
        )
        self.live_diagnostics_text.pack(fill="x", pady=(6, 0))

    def open_song_workspace(self) -> None:
        super().open_song_workspace()
        window = self._workspace_window
        if window is not None and window.winfo_exists():
            window.configure(background=PALETTE.canvas)
            window.title(window_title("Song Workspace"))
            polish_widget_tree(window)

    def _show_full_activity_log(self) -> None:
        notebook = self.log_tab.master
        if isinstance(notebook, ttk.Notebook):
            notebook.select(self.log_tab)

    def _append_live_diagnostic(self, line: str) -> None:
        if not hasattr(self, "live_diagnostics_text"):
            return
        widget = self.live_diagnostics_text
        widget.configure(state="normal")
        widget.insert("end", line.rstrip() + "\n")
        lines = int(widget.index("end-1c").split(".")[0])
        if lines > 8:
            widget.delete("1.0", f"{lines - 8}.0")
        widget.see("end")
        widget.configure(state="disabled")

    def _render_persisted_diagnostics(self) -> None:
        if not hasattr(self, "live_diagnostics_text"):
            return
        lines = read_recent_project_diagnostics(self.project, limit=8)
        widget = self.live_diagnostics_text
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if lines:
            widget.insert("end", "\n".join(lines) + "\n")
        else:
            widget.insert("end", "No project diagnostics recorded yet.\n")
        widget.configure(state="disabled")

    def _log(self, message: str) -> None:
        line = format_diagnostic_line(message)
        super()._log(line)
        persist_project_diagnostic(self.project, message)
        self._append_live_diagnostic(line)

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        if busy:
            self._active_diagnostic_task = message or "Background operation"
        super()._set_busy(busy, message)

    def _background_succeeded(self, result, on_success) -> None:
        label = self._active_diagnostic_task or "Background operation"
        self._log(f"Completed: {label}")
        self._active_diagnostic_task = ""
        super()._background_succeeded(result, on_success)

    def _background_failed(self, exc: Exception, details: str) -> None:
        label = self._active_diagnostic_task or "Background operation"
        self._log(f"ERROR: {label} failed: {type(exc).__name__}: {exc}")
        self._active_diagnostic_task = ""
        super()._background_failed(exc, details)

    def load_project(self, project: Path) -> bool:
        """Load one project and report actual success for diagnostic lifecycle events."""

        requested = project.expanduser().resolve()
        self._diagnostic_project_load_in_progress = True
        try:
            try:
                manifest = ProjectManifest.load(requested)
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"Could not open project:\n{exc}", parent=self)
                return False

            self.project = requested
            self.project_var.set(str(requested))
            self.song_var.set(manifest.project_name)
            self._remember_project(requested)
            self._log(f"Opened project: {requested}")
            self.refresh_project()
        finally:
            self._diagnostic_project_load_in_progress = False

        self._last_workflow_diagnostic = ""
        self._render_persisted_diagnostics()
        self._log(f"Project opened: {requested.name}")
        # Reuse the state already established by the refresh_project() call above
        # (still inside the try/finally) instead of re-running the whole
        # DesktopApp/ProductDesktopApp/GuidedDesktopApp refresh cascade -- workflow
        # plan recomputation, Song Workspace/tone-regions/xml-export/dlcbuilder
        # window refreshes, and track-table rebuilds -- a second time just to log
        # one diagnostic line (#304/#193: redundant duplicate-refresh workflow
        # friction on every project open).
        self._log_workflow_state_if_changed()
        return True

    def refresh_project(self) -> None:
        super().refresh_project()
        if self._diagnostic_project_load_in_progress:
            return
        self._log_workflow_state_if_changed()

    def _log_workflow_state_if_changed(self) -> None:
        if not hasattr(self, "readiness_headline_var"):
            return
        state = workflow_diagnostic_key(
            self.project,
            self.readiness_headline_var.get(),
            self.readiness_detail_var.get(),
        )
        if state != self._last_workflow_diagnostic:
            self._last_workflow_diagnostic = state
            self._log(
                f"Workflow state: {self.readiness_headline_var.get()} — {self.readiness_detail_var.get()}"
            )


def main() -> None:
    app = LiveDiagnosticsGuidedDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
