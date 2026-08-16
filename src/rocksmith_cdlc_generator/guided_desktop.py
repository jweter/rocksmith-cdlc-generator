from __future__ import annotations

from pathlib import Path
from typing import Literal
import tkinter as tk
from tkinter import ttk

from .desktop_shell import ProductDesktopApp
from .multi_arrangement_plan import build_multi_arrangement_workflow_plan
from .song_readiness import SongReadiness, build_song_readiness


GuidedActionRoute = Literal["automatic", "score", "rights", "song-review", "workflow"]


class GuidedDesktopApp(ProductDesktopApp):
    """Primary product shell that puts user progress ahead of pipeline details."""

    def _build_layout(self) -> None:
        super()._build_layout()
        self.run_button.configure(text="Continue Automatically")

        self.readiness_headline_var = tk.StringVar(value="Open or create a song project to begin")
        self.readiness_detail_var = tk.StringVar(
            value="Choose one recording and, when available, one complete score for Bass, Lead, and Rhythm."
        )
        self.readiness_percent_var = tk.DoubleVar(value=0.0)
        self.readiness_percent_text_var = tk.StringVar(value="0% prepared")
        self._guided_action_route: GuidedActionRoute | None = None

        children = self.winfo_children()
        before = children[1] if len(children) > 1 else None
        readiness = ttk.LabelFrame(self, text="Song progress", padding=12)
        pack_options = {"fill": "x", "padx": 12, "pady": (0, 8)}
        if before is not None:
            pack_options["before"] = before
        readiness.pack(**pack_options)

        header = ttk.Frame(readiness)
        header.pack(fill="x")
        ttk.Label(
            header,
            textvariable=self.readiness_headline_var,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")
        ttk.Label(header, textvariable=self.readiness_percent_text_var).pack(side="right")

        self.readiness_progress = ttk.Progressbar(
            readiness,
            maximum=100,
            variable=self.readiness_percent_var,
        )
        self.readiness_progress.pack(fill="x", pady=(8, 8))

        action_row = ttk.Frame(readiness)
        action_row.pack(fill="x")
        ttk.Label(
            action_row,
            textvariable=self.readiness_detail_var,
            wraplength=820,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        self.next_action_button = ttk.Button(
            action_row,
            text="Next Step",
            command=self._run_guided_action,
            state="disabled",
        )
        self.next_action_button.pack(side="right", padx=(12, 0))

    @staticmethod
    def readiness_display(readiness: SongReadiness) -> tuple[str, str]:
        headline = f"{readiness.percent}% prepared — {readiness.headline}"
        if readiness.next_action is None:
            detail = "No remaining authoring workflow action is currently required."
        elif readiness.next_action.kind == "needs_you":
            detail = f"Needs you next: {readiness.next_action.title}. {readiness.next_action.detail}"
        elif readiness.next_action.kind == "automatic":
            detail = f"Ready next: {readiness.next_action.title}. Use Continue Automatically."
        else:
            detail = f"Next: {readiness.next_action.title}. {readiness.next_action.detail}"
        return headline, detail

    @staticmethod
    def guided_action_spec(readiness: SongReadiness) -> tuple[str, GuidedActionRoute] | None:
        """Return the safest direct UI destination for the current actionable step."""

        action = readiness.next_action
        if action is None:
            return None
        if action.kind == "automatic":
            return ("Continue Automatically", "automatic")

        routes: dict[str, tuple[str, GuidedActionRoute]] = {
            "source-rights": ("Review Source Rights", "rights"),
            "score-arrangements": ("Review Score Tracks", "score"),
            "align-tab": ("Open Song Review", "song-review"),
            "shared-timeline": ("Open Song Review", "song-review"),
            "human-review": ("Open Song Review", "song-review"),
        }
        if action.step_id in routes:
            return routes[action.step_id]
        if action.kind == "needs_you":
            # Unknown or advanced human gates remain visible without guessing which
            # specific editor grants that authority. The workflow tab is diagnostic only.
            return ("Show Workflow Details", "workflow")
        return None

    def _select_primary_tab(self, tab: ttk.Frame) -> None:
        notebook = tab.master
        if isinstance(notebook, ttk.Notebook):
            notebook.select(tab)

    def _run_guided_action(self) -> None:
        route = self._guided_action_route
        if route == "automatic":
            self.run_automatic_steps()
        elif route == "score":
            self._select_primary_tab(self.score_tab)
            self.mapping_combos[next(iter(self.mapping_combos))].focus_set()
        elif route == "rights":
            self._select_primary_tab(self.rights_tab)
            self.rights_source_combo.focus_set()
        elif route == "song-review":
            self.open_song_workspace()
        elif route == "workflow":
            self._select_primary_tab(self.workflow_tab)

    def _update_guided_action(self, readiness: SongReadiness) -> None:
        spec = self.guided_action_spec(readiness)
        if spec is None:
            self._guided_action_route = None
            self.next_action_button.configure(text="Next Step", state="disabled")
            return
        label, route = spec
        self._guided_action_route = route
        self.next_action_button.configure(text=label, state="normal")

    def refresh_project(self) -> None:
        super().refresh_project()
        project = self.project
        if project is None or not (Path(project) / "project.json").is_file():
            self._guided_action_route = None
            if hasattr(self, "next_action_button"):
                self.next_action_button.configure(text="Next Step", state="disabled")
            return
        try:
            readiness = build_song_readiness(build_multi_arrangement_workflow_plan(project))
        except Exception:
            # The detailed project refresh already reports planner failures. Keep this
            # presentation layer from obscuring that authoritative error path.
            self._guided_action_route = None
            self.next_action_button.configure(text="Next Step", state="disabled")
            return
        headline, detail = self.readiness_display(readiness)
        self.readiness_headline_var.set(headline)
        self.readiness_detail_var.set(detail)
        self.readiness_percent_var.set(float(readiness.percent))
        self.readiness_percent_text_var.set(f"{readiness.percent}% prepared")
        self._update_guided_action(readiness)


def main() -> None:
    app = GuidedDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
