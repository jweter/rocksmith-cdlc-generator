from __future__ import annotations

from pathlib import Path
from typing import Callable
import tkinter as tk
from tkinter import ttk

from .desktop_xml_export import ArrangementName

ExportSucceeded = Callable[[dict[str, Path]], None]
ExportFailed = Callable[[Exception], None]
ExportRequest = Callable[[ArrangementName, ExportSucceeded, ExportFailed], bool]


class RocksmithXmlExportWindow(tk.Toplevel):
    """Product-facing launcher for the existing validation-gated arrangement exporters."""

    def __init__(
        self,
        parent: tk.Misc,
        project: Path,
        *,
        export_request: ExportRequest,
    ) -> None:
        super().__init__(parent)
        self.project = project.expanduser().resolve()
        self._export_request = export_request
        self.title("Rocksmith XML Export — Rocksmith CDLC Generator")
        self.geometry("900x420")
        self.minsize(760, 360)

        ttk.Label(
            self,
            text=(
                "Export one validation-gated Rocksmith 2014 XML arrangement at a time. "
                "An export request does not approve warnings, musical edits, tones, package readiness, or installation."
            ),
            wraplength=850,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(12, 10))

        self.status_vars: dict[ArrangementName, tk.StringVar] = {}
        table = ttk.Frame(self, padding=(12, 0, 12, 0))
        table.pack(fill="x")
        table.columnconfigure(1, weight=1)

        for row, arrangement in enumerate(("bass", "lead", "rhythm")):
            typed_arrangement: ArrangementName = arrangement
            ttk.Label(table, text=arrangement.title(), width=10).grid(
                row=row, column=0, sticky="w", pady=7
            )
            status = tk.StringVar(value="Not exported in this session")
            self.status_vars[typed_arrangement] = status
            ttk.Label(table, textvariable=status, wraplength=600).grid(
                row=row, column=1, sticky="ew", padx=(8, 10), pady=7
            )
            ttk.Button(
                table,
                text="Export XML",
                command=lambda selected=typed_arrangement: self._request(selected),
            ).grid(row=row, column=2, sticky="e", pady=7)

        ttk.Separator(self).pack(fill="x", padx=12, pady=12)
        ttk.Label(
            self,
            text=(
                "Existing XML files are not treated as current merely because they exist. "
                "Use the Song Workspace Validation tab for current readiness; each export re-runs its authoritative gate."
            ),
            wraplength=850,
            justify="left",
        ).pack(anchor="w", padx=12)

    def set_project(self, project: Path) -> None:
        self.project = project.expanduser().resolve()
        for status in self.status_vars.values():
            status.set("Not exported in this session")

    def _request(self, arrangement: ArrangementName) -> None:
        accepted = self._export_request(
            arrangement,
            lambda outputs, selected=arrangement: self._succeeded(selected, outputs),
            lambda error, selected=arrangement: self._failed(selected, error),
        )
        if accepted:
            self.status_vars[arrangement].set(
                "Export requested; authoritative validation gate is running…"
            )
        else:
            self.status_vars[arrangement].set(
                "Export not started because another desktop operation is already running."
            )

    def _succeeded(self, arrangement: ArrangementName, outputs: dict[str, Path]) -> None:
        xml_path = outputs.get("xml")
        if xml_path is None:
            self.status_vars[arrangement].set("Export completed, but no XML path was returned.")
            return
        self.status_vars[arrangement].set(f"Exported: {xml_path}")

    def _failed(self, arrangement: ArrangementName, error: Exception) -> None:
        self.status_vars[arrangement].set(f"Export failed: {error}")
