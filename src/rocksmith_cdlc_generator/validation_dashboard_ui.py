from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .design_tokens import STATUS_STYLES, TYPOGRAPHY, spacing
from .song_workspace import SongWorkspaceSnapshot
from .validation import format_actionable_warning_compact
from .validation_dashboard import build_validation_dashboard
from .validation_dashboard_presentation import present_validation_row


class ValidationDashboardPanel(ttk.Frame):
    """Read-only Bass/Lead/Rhythm validation dashboard for the Song Workspace."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.summary_var = tk.StringVar(value="Validation state has not been loaded yet.")
        ttk.Label(
            self,
            textvariable=self.summary_var,
            font=TYPOGRAPHY["subheading"].as_tuple(),
            wraplength=1160,
        ).pack(anchor="w", pady=(0, spacing("sm")))
        ttk.Label(
            self,
            text=(
                "This dashboard summarizes persisted validation authority only. It does not approve review findings, "
                "promote XML, or bypass any human gate."
            ),
            font=TYPOGRAPHY["body"].as_tuple(),
            wraplength=1160,
        ).pack(anchor="w", pady=(0, spacing("md")))

        self.tree = ttk.Treeview(
            self,
            columns=("role", "state", "validation", "fails", "warnings", "xml", "next"),
            show="headings",
            height=8,
        )
        specs = (
            ("role", "Arrangement", 110),
            ("state", "Dashboard state", 190),
            ("validation", "Validation", 210),
            ("fails", "Fails", 65),
            ("warnings", "Warnings (actionable/raw)", 150),
            ("xml", "Rocksmith XML", 210),
            ("next", "Next action", 520),
        )
        for key, title, width in specs:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        for state, token in STATUS_STYLES.items():
            self.tree.tag_configure(state, foreground=token.foreground)
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
            presentation = present_validation_row(row)
            self.tree.insert(
                "",
                "end",
                values=(
                    row.role.title(),
                    presentation.dashboard_text,
                    presentation.validation_text,
                    row.fail_count,
                    format_actionable_warning_compact(row.actionable_warning_count, row.warning_count),
                    presentation.xml_text,
                    row.next_action,
                ),
                tags=(presentation.status_state,),
            )
