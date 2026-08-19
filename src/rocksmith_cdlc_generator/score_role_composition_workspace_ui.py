from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .score_role_composition_workspace_controls import (
    ScoreRoleCompositionWorkspaceControl,
    build_score_role_composition_workspace_controls,
    compose_role_composition_from_workspace,
)


class ScoreRoleCompositionWorkspaceMixin:
    """Add read-only multi-track composition status and a no-overlap compose action.

    This mirrors ``TrackTrustWorkspaceMixin``: it reuses the existing arrangement role
    selector as the authority for which role the panel describes and never mutates
    project data outside the one explicit "Compose From Selected Tracks" action, which
    itself only proceeds when the current status reports zero unresolved cross-track
    overlaps for that role. Resolving overlaps remains a `cdlc-score-composition`
    CLI-only workflow until a later slice adds an in-workspace overlap-decision UI.
    """

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()

        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Multi-track score composition",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))

        row = ttk.Frame(box)
        row.pack(fill="x")
        self.score_composition_status_var = tk.StringVar(
            value="Composition status becomes available after score mapping."
        )
        ttk.Label(
            row,
            textvariable=self.score_composition_status_var,
            wraplength=820,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        self.compose_score_role_button = ttk.Button(
            row,
            text="Compose From Selected Tracks",
            command=self._compose_score_role_composition,
            state="disabled",
        )
        self.compose_score_role_button.pack(side="right", padx=(12, 0))

        self.score_composition_blocker_var = tk.StringVar(value="")
        ttk.Label(
            box,
            textvariable=self.score_composition_blocker_var,
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            box,
            text=(
                "Composing here only merges the currently selected score tracks for this "
                "role and only when no cross-track overlap needs a human decision. Adding "
                "tracks to a role's selection and resolving overlaps remain "
                "cdlc-score-composition CLI workflows for now."
            ),
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # The existing arrangement role selector is the authority for which role the
        # panel describes. Refreshing on role changes does not mutate project data.
        self.fretboard_role_var.trace_add("write", self._score_composition_role_changed)

    def refresh(self) -> None:
        super().refresh()
        self._refresh_score_composition_panel()

    def _score_composition_role_changed(self, *_args) -> None:
        if hasattr(self, "score_composition_status_var"):
            self._refresh_score_composition_panel()

    def _selected_score_composition_control(self) -> ScoreRoleCompositionWorkspaceControl | None:
        role = self.fretboard_role_var.get().strip().lower()
        if role not in {"bass", "lead", "rhythm"}:
            return None
        controls = build_score_role_composition_workspace_controls(self.project)
        return controls.control_for(role)

    def _refresh_score_composition_panel(self) -> None:
        if not hasattr(self, "score_composition_status_var"):
            return
        try:
            control = self._selected_score_composition_control()
        except Exception as exc:
            self.score_composition_status_var.set(f"Composition status unavailable: {exc}")
            self.score_composition_blocker_var.set("")
            self.compose_score_role_button.configure(
                text="Compose From Selected Tracks",
                state="disabled",
            )
            return

        if control is None:
            self.score_composition_status_var.set(
                "Select a Bass, Lead, or Rhythm arrangement to review its composition status."
            )
            self.score_composition_blocker_var.set("")
            self.compose_score_role_button.configure(
                text="Compose From Selected Tracks",
                state="disabled",
            )
            return

        self.score_composition_status_var.set(control.status_text)
        self.score_composition_blocker_var.set(control.blocker_text or "")
        self.compose_score_role_button.configure(
            text=control.compose_button_text,
            state="normal" if control.compose_button_enabled else "disabled",
        )

    def _compose_score_role_composition(self) -> None:
        role = self.fretboard_role_var.get().strip().lower()
        if role not in {"bass", "lead", "rhythm"}:
            return
        try:
            controls = compose_role_composition_from_workspace(self.project, arrangement=role)
            control = controls.control_for(role)
        except Exception as exc:
            messagebox.showerror("Song Workspace Score Composition", str(exc), parent=self)
            self._refresh_score_composition_panel()
            return

        self.refresh()
        if control is not None:
            self.score_composition_status_var.set(control.status_text)
