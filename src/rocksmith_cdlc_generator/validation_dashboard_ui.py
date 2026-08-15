from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .song_workspace import SongWorkspaceSnapshot
from .validation_dashboard import build_validation_dashboard


class ValidationDashboardPanel(ttk.Frame):
    """Read-only Bass/Lead/Rhythm validation dashboard for the Song Workspace."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.summary_var = tk.StringVar(value="Validation state has not been loaded yet.")
        ttk.Label(
            self,
            textvariable=self.summary_var,
            font=("Segoe UI", 11, "bold"),
            wraplength=1160,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self,
            text=(
                "This dashboard summarizes persisted validation authority only. It does not approve review findings, "
                "promote XML, or bypass any human gate."
            ),
            wraplength=1160,
        ).pack(anchor="w", pady=(0, 10))

        self.tree = ttk.Treeview(
            self,
            columns=("role", "state", "validation", "fails", "warnings", "xml", "next"),
            show="headings",
            height=8,
        )
        specs = (
            ("role", "Arrangement", 110),
            ("state", "Dashboard state", 150),
            ("validation", "Validation", 115),
            ("fails", "Fails", 65),
            ("warnings", "Warnings", 75),
            ("xml", "Rocksmith XML", 120),
            ("next", "Next action", 620),
        )
        for key, title, width in specs:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)

    def refresh_from_snapshot(self, snapshot: SongWorkspaceSnapshot) -> None:
        dashboard = build_validation_dashboard(snapshot)
        self.summary_var.set(
            f"{dashboard.headline}  "
            f"Configured: {dashboard.configured_count} · "
            f"Blocked: {dashboard.blocked_count} · "
            f"Needs validation: {dashboard.validation_needed_count} · "
            f"XML ready: {dashboard.xml_ready_count}"
        )
        self.tree.delete(*self.tree.get_children())
        for row in dashboard.rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    row.role.title(),
                    row.state.replace("_", " "),
                    row.validation_state,
                    row.fail_count,
                    row.warning_count,
                    "ready" if row.export_xml_ready else "not ready",
                    row.next_action,
                ),
            )
