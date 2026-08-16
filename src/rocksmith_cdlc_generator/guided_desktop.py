from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .desktop_shell import ProductDesktopApp
from .multi_arrangement_plan import build_multi_arrangement_workflow_plan
from .song_readiness import SongReadiness, build_song_readiness


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
        ttk.Button(
            action_row,
            text="Open Song Review",
            command=self.open_song_workspace,
        ).pack(side="right", padx=(12, 0))

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

    def refresh_project(self) -> None:
        super().refresh_project()
        project = self.project
        if project is None or not (Path(project) / "project.json").is_file():
            return
        try:
            readiness = build_song_readiness(build_multi_arrangement_workflow_plan(project))
        except Exception:
            # The detailed project refresh already reports planner failures. Keep this
            # presentation layer from obscuring that authoritative error path.
            return
        headline, detail = self.readiness_display(readiness)
        self.readiness_headline_var.set(headline)
        self.readiness_detail_var.set(detail)
        self.readiness_percent_var.set(float(readiness.percent))
        self.readiness_percent_text_var.set(f"{readiness.percent}% prepared")


def main() -> None:
    app = GuidedDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
