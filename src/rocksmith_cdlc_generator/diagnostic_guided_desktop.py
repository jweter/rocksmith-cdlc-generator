from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

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
from .printed_score_desktop_actions import (
    build_latest_reviewed_practice,
    recognize_printed_score_for_review,
)
from .printed_score_project import create_printed_score_project, is_printed_score_project
from .printed_score_project_dialog import ask_printed_score_project_request
from .printed_score_review_ui import open_printed_score_review
from .score_measure_recognition import PRIVATE_RECOGNITION_RELATIVE_PATH
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

    def _printed_score_progress(self) -> tuple[int, str, str]:
        if self.project is None:
            return 0, "Printed score project", "Create or open a printed-score project."
        recognition_dir = self.project / PRIVATE_RECOGNITION_RELATIVE_PATH
        candidates = list(recognition_dir.glob("*-candidates.json")) if recognition_dir.is_dir() else []
        reviewed = list(recognition_dir.glob("*-reviewed-fixture.json")) if recognition_dir.is_dir() else []
        practice_dir = self.project / "printed_notation"
        built = (practice_dir / "arr_bass_RS2.xml").is_file() and (practice_dir / "click.wav").is_file()
        if built:
            return 100, "Printed score practice build ready", "The reviewed Rocksmith XML and click track are ready for the next packaging/test step."
        if reviewed:
            return 75, "Printed score review complete", "Use Build Practice to generate the validated Rocksmith XML and count-in click track."
        if candidates:
            return 45, "Printed score recognition ready for review", "Use Review to verify/correct every recognized measure before promotion."
        return 15, "Private printed score registered", "Use Recognize to process the first page locally with Ollama, then review the result."

    def _update_guided_action(self, readiness: SongReadiness) -> None:
        super()._update_guided_action(readiness)
        if self.project is not None and is_printed_score_project(self.project):
            percent, headline, detail = self._printed_score_progress()
            self._guided_action_route = None
            self.next_action_button.configure(text="Use Printed Score Practice", state="disabled")
            self.run_button.configure(state="disabled")
            self.readiness_percent_var.set(float(percent))
            self.readiness_percent_text_var.set(f"{percent}% through printed-score proof of concept")
            self.readiness_headline_var.set(headline)
            self.readiness_detail_var.set(detail)
        elif not getattr(self, "_busy", False):
            self.run_button.configure(state="normal")
        self._sync_next_required_marker()

    def _build_layout(self) -> None:
        super()._build_layout()
        children = self.winfo_children()
        before = children[-1] if children else None

        score_frame = ttk.LabelFrame(self, text="Printed score practice", padding=8)
        score_options = {"fill": "x", "padx": 12, "pady": (0, 8)}
        if before is not None:
            score_options["before"] = before
        score_frame.pack(**score_options)
        ttk.Label(
            score_frame,
            text=(
                "Create a score-only project, recognize notation/TAB locally, review every "
                "measure, then build a validated click-track Rocksmith practice arrangement."
            ),
            wraplength=560,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        score_actions = ttk.Frame(score_frame)
        score_actions.pack(side="right", padx=(12, 0))
        ttk.Button(
            score_actions,
            text="New Score Project…",
            command=self._create_printed_score_project,
        ).pack(side="left")
        ttk.Button(
            score_actions,
            text="Recognize…",
            command=self._recognize_printed_score,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            score_actions,
            text="Review…",
            command=self._open_printed_score_review,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            score_actions,
            text="Build Practice",
            command=self._build_printed_score_practice,
        ).pack(side="left", padx=(6, 0))

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

    def _create_printed_score_project(self) -> None:
        request = ask_printed_score_project_request(self)
        if request is None:
            return

        def completed(project: Path) -> None:
            self._log(f"Created private printed-score project: {project}")
            self.load_project(project)
            messagebox.showinfo(
                APP_TITLE,
                "Printed-score project created and opened.\n\nNext: click Recognize… to run the first local measure-recognition pass.",
                parent=self,
            )

        def failed(error: Exception) -> None:
            messagebox.showerror(
                APP_TITLE,
                f"Could not create printed-score project:\n{error}",
                parent=self,
            )

        self._run_background(
            "Creating private printed-score project and verifying page hashes…",
            lambda: create_printed_score_project(
                spec_path=request.spec_path,
                source_dir=request.source_dir,
                projects_root=request.projects_root,
                movement_id=request.movement_id,
            ),
            completed,
            failed,
        )

    def _recognize_printed_score(self) -> None:
        if self.project is None or not is_printed_score_project(self.project):
            messagebox.showinfo(
                APP_TITLE,
                "Open or create a private printed-score project first.",
                parent=self,
            )
            return

        page = simpledialog.askinteger(
            "Printed Score Recognition",
            "Printed page number to recognize:",
            parent=self,
            initialvalue=2,
            minvalue=1,
        )
        if page is None:
            return
        model = simpledialog.askstring(
            "Printed Score Recognition",
            "Local Ollama vision model:",
            parent=self,
            initialvalue="gemma3:4b",
        )
        if not model:
            return
        limit = simpledialog.askinteger(
            "Printed Score Recognition",
            "How many measures should be recognized in this pass?",
            parent=self,
            initialvalue=8,
            minvalue=1,
            maxvalue=32,
        )
        if limit is None:
            return
        expected_systems = simpledialog.askinteger(
            "Printed Score Recognition",
            "Expected notation/TAB systems on the page (use 5 for the current Prelude page 2):",
            parent=self,
            initialvalue=5,
            minvalue=1,
            maxvalue=20,
        )
        if expected_systems is None:
            return

        project = self.project

        def is_current_project() -> bool:
            return self.project is not None and self.project.resolve() == project.resolve()

        def completed(result) -> None:
            _candidates, candidate_path = result
            self._log(f"Printed-score recognition candidates ready: {candidate_path.name}")
            self.refresh_project()
            self._show_printed_score_review(candidate_path)

        def failed(error: Exception) -> None:
            messagebox.showerror(
                APP_TITLE,
                f"Printed-score recognition failed:\n{error}",
                parent=self,
            )

        self._run_background(
            f"Recognizing printed score page {page} locally with {model}…",
            lambda: recognize_printed_score_for_review(
                project,
                printed_page=page,
                model=model,
                limit=limit,
                expected_system_count=expected_systems,
            ),
            completed,
            failed,
            is_current_project,
        )

    def _show_printed_score_review(self, candidate: Path) -> None:
        if self.project is None:
            return
        try:
            window = open_printed_score_review(self, self.project, candidate)
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Could not open printed-score review:\n{exc}",
                parent=self,
            )
            return
        self._log(f"Opened printed-score human review: {candidate.name}")
        window.transient(self)
        window.focus_set()

    def _open_printed_score_review(self) -> None:
        if self.project is None or not is_printed_score_project(self.project):
            messagebox.showinfo(
                APP_TITLE,
                "Open or create a private printed-score project first.",
                parent=self,
            )
            return

        recognition_dir = self.project / PRIVATE_RECOGNITION_RELATIVE_PATH
        recognition_dir.mkdir(parents=True, exist_ok=True)
        candidates = sorted(
            recognition_dir.glob("*-candidates.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            messagebox.showinfo(
                APP_TITLE,
                "No recognition candidates exist yet. Click Recognize… first.",
                parent=self,
            )
            return

        if len(candidates) == 1:
            candidate = candidates[0]
        else:
            selected = filedialog.askopenfilename(
                parent=self,
                title="Choose printed-score recognition candidates",
                initialdir=str(recognition_dir),
                filetypes=(("Recognition candidates", "*-candidates.json"), ("JSON", "*.json")),
            )
            if not selected:
                return
            candidate = Path(selected)
        self._show_printed_score_review(candidate)

    def _build_printed_score_practice(self) -> None:
        if self.project is None or not is_printed_score_project(self.project):
            messagebox.showinfo(
                APP_TITLE,
                "Open or create a private printed-score project first.",
                parent=self,
            )
            return
        count_in = simpledialog.askinteger(
            "Printed Score Practice",
            "Count-in measures:",
            parent=self,
            initialvalue=2,
            minvalue=0,
            maxvalue=8,
        )
        if count_in is None:
            return
        project = self.project

        def is_current_project() -> bool:
            return self.project is not None and self.project.resolve() == project.resolve()

        def completed(outputs: dict[str, Path]) -> None:
            lines = [f"{name}: {path}" for name, path in sorted(outputs.items())]
            self._log("Built validated printed-score practice XML and click track.")
            messagebox.showinfo(
                APP_TITLE,
                "Printed-score practice build complete:\n\n" + "\n".join(lines),
                parent=self,
            )
            self.refresh_project()

        def failed(error: Exception) -> None:
            messagebox.showerror(
                APP_TITLE,
                f"Printed-score practice build failed:\n{error}",
                parent=self,
            )

        self._run_background(
            "Building reviewed printed-score Rocksmith practice output…",
            lambda: build_latest_reviewed_practice(
                project,
                count_in_measures=count_in,
            ),
            completed,
            failed,
            is_current_project,
        )

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
