from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .arrangement_edit_history import (
    load_current_arrangement_edit_history,
    redo_arrangement_edit,
    undo_arrangement_edit,
)
from .chord_identity_ui import ChordIdentitySongWorkspaceWindow


class ArrangementEditHistorySongWorkspaceWindow(ChordIdentitySongWorkspaceWindow):
    """Song Workspace with provenance-safe undo/redo for accepted arrangement edits."""

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Accepted arrangement edit history",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill="x")
        self.undo_edit_button = ttk.Button(
            row,
            text="Undo Accepted Edit",
            command=self._undo_accepted_edit,
            state="disabled",
        )
        self.undo_edit_button.pack(side="left")
        self.redo_edit_button = ttk.Button(
            row,
            text="Redo Accepted Edit",
            command=self._redo_accepted_edit,
            state="disabled",
        )
        self.redo_edit_button.pack(side="left", padx=(6, 0))
        self.edit_history_status_var = tk.StringVar(
            value="Accepted position, timing, technique, fingering, and chord-identity edits become reversible here."
        )
        ttk.Label(
            row,
            textvariable=self.edit_history_status_var,
            wraplength=900,
            justify="left",
        ).pack(side="left", fill="x", expand=True, padx=(14, 0))

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "undo_edit_button"):
            self._sync_edit_history_controls()

    def _sync_edit_history_controls(self) -> None:
        self.undo_edit_button.configure(state="disabled")
        self.redo_edit_button.configure(state="disabled")
        try:
            history = load_current_arrangement_edit_history(self.project)
        except (OSError, ValueError) as exc:
            self.edit_history_status_var.set(
                f"Edit history unavailable until authority is current: {exc}"
            )
            return

        if history.can_undo:
            self.undo_edit_button.configure(state="normal")
        if history.can_redo:
            self.redo_edit_button.configure(state="normal")

        applied = history.cursor
        total = len(history.transactions)
        if total == 0:
            self.edit_history_status_var.set(
                "No accepted arrangement edits have been recorded for current authority."
            )
            return
        previous = history.transactions[applied - 1].kind if applied else None
        upcoming = history.transactions[applied].kind if applied < total else None
        details = [f"{applied}/{total} accepted edit transaction(s) applied"]
        if previous is not None:
            details.append(f"undo: {previous.replace('_', ' ')}")
        if upcoming is not None:
            details.append(f"redo: {upcoming.replace('_', ' ')}")
        self.edit_history_status_var.set(" · ".join(details))

    def _undo_accepted_edit(self) -> None:
        try:
            transaction = undo_arrangement_edit(self.project)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Arrangement Edit History", str(exc), parent=self)
            self._sync_edit_history_controls()
            return
        self.refresh()
        self.edit_history_status_var.set(
            f"Undid accepted {transaction.kind.replace('_', ' ')} edit by restoring the exact prior review authority."
        )

    def _redo_accepted_edit(self) -> None:
        try:
            transaction = redo_arrangement_edit(self.project)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Arrangement Edit History", str(exc), parent=self)
            self._sync_edit_history_controls()
            return
        self.refresh()
        self.edit_history_status_var.set(
            f"Redid accepted {transaction.kind.replace('_', ' ')} edit by restoring the exact recorded review authority."
        )
