from __future__ import annotations

from pathlib import Path
import tkinter as tk

from .metadata_cover_ui import MetadataCoverPanel


class MetadataCoverWindow(tk.Toplevel):
    """Separate composed build-presentation surface; owns no musical authority."""

    def __init__(self, parent: tk.Misc, project: Path) -> None:
        super().__init__(parent)
        self.project = project.expanduser().resolve()
        self.title("Metadata & Cover — Rocksmith CDLC Generator")
        self.geometry("980x430")
        self.minsize(760, 360)
        self.panel = MetadataCoverPanel(self)
        self.panel.pack(fill="both", expand=True, padx=12, pady=12)
        self.panel.set_project(self.project)

    def set_project(self, project: Path) -> None:
        self.project = project.expanduser().resolve()
        self.panel.set_project(self.project)

    def refresh(self) -> None:
        self.panel.refresh()
