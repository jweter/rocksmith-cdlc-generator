from __future__ import annotations

from pathlib import Path
import tkinter as tk

from .tone_regions_ui import ToneRegionsPanel


class ToneRegionsWindow(tk.Toplevel):
    """Separate composed tone-region surface; owns package tone timing only."""

    def __init__(self, parent: tk.Misc, project: Path) -> None:
        super().__init__(parent)
        self.project = project.expanduser().resolve()
        self.title("Tones & Regions — Rocksmith CDLC Generator")
        self.geometry("980x620")
        self.minsize(760, 500)
        self.panel = ToneRegionsPanel(self)
        self.panel.pack(fill="both", expand=True, padx=12, pady=12)
        self.panel.set_project(self.project)

    def set_project(self, project: Path) -> None:
        self.project = project.expanduser().resolve()
        self.panel.set_project(self.project)

    def refresh(self) -> None:
        self.panel.refresh()
