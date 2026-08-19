from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .score_role_composition_workspace_controls import (
    ScoreRoleCompositionWorkspaceControl,
    add_score_composition_track,
    build_score_role_composition_workspace_controls,
    compose_role_composition_from_workspace,
    remove_score_composition_track,
)


class ScoreRoleCompositionWorkspaceMixin:
    """Add multi-track composition status, a track picker, and a no-overlap compose action.

    This mirrors ``TrackTrustWorkspaceMixin``: it reuses the existing arrangement role
    selector as the authority for which role the panel describes and never mutates
    project data outside three explicit actions: adding an available score track to a
    role's selection, removing a previously added (non-primary) track, and composing
    the role's currently selected tracks, which itself only proceeds when the current
    status reports zero unresolved cross-track overlaps for that role. Resolving
    overlaps remains a `cdlc-score-composition` CLI-only workflow until a later slice
    adds an in-workspace overlap-decision UI.
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

        add_row = ttk.Frame(box)
        add_row.pack(fill="x", pady=(6, 0))
        ttk.Label(add_row, text="Add track:").pack(side="left")
        self.score_composition_add_var = tk.StringVar(value="")
        self.score_composition_add_combo = ttk.Combobox(
            add_row, textvariable=self.score_composition_add_var, state="readonly", width=42
        )
        self.score_composition_add_combo.pack(side="left", padx=(6, 6))
        self.add_score_composition_track_button = ttk.Button(
            add_row,
            text="Add Track",
            command=self._add_score_composition_track,
            state="disabled",
        )
        self.add_score_composition_track_button.pack(side="left")

        remove_row = ttk.Frame(box)
        remove_row.pack(fill="x", pady=(6, 0))
        ttk.Label(remove_row, text="Remove track:").pack(side="left")
        self.score_composition_remove_var = tk.StringVar(value="")
        self.score_composition_remove_combo = ttk.Combobox(
            remove_row, textvariable=self.score_composition_remove_var, state="readonly", width=42
        )
        self.score_composition_remove_combo.pack(side="left", padx=(6, 6))
        self.remove_score_composition_track_button = ttk.Button(
            remove_row,
            text="Remove Track",
            command=self._remove_score_composition_track,
            state="disabled",
        )
        self.remove_score_composition_track_button.pack(side="left")

        ttk.Label(
            box,
            text=(
                "Adding a track only adds it to this role's selection; composing (above) "
                "still requires zero unresolved cross-track overlaps. The role's confirmed "
                "primary track can never be removed here. Resolving cross-track overlaps "
                "remains a cdlc-score-composition CLI workflow for now."
            ),
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self._score_composition_add_options: dict[str, int] = {}
        self._score_composition_remove_options: dict[str, int] = {}

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

    def _reset_score_composition_pickers(self) -> None:
        self._score_composition_add_options = {}
        self._score_composition_remove_options = {}
        self.score_composition_add_combo.configure(values=[])
        self.score_composition_add_var.set("")
        self.add_score_composition_track_button.configure(state="disabled")
        self.score_composition_remove_combo.configure(values=[])
        self.score_composition_remove_var.set("")
        self.remove_score_composition_track_button.configure(state="disabled")

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
            self._reset_score_composition_pickers()
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
            self._reset_score_composition_pickers()
            return

        self.score_composition_status_var.set(control.status_text)
        self.score_composition_blocker_var.set(control.blocker_text or "")
        self.compose_score_role_button.configure(
            text=control.compose_button_text,
            state="normal" if control.compose_button_enabled else "disabled",
        )

        self._score_composition_add_options = {
            option.label: option.source_track_index for option in control.available_tracks
        }
        self.score_composition_add_combo.configure(values=list(self._score_composition_add_options))
        if self.score_composition_add_var.get() not in self._score_composition_add_options:
            self.score_composition_add_var.set(
                next(iter(self._score_composition_add_options), "")
            )
        self.add_score_composition_track_button.configure(
            state="normal" if control.add_track_enabled else "disabled"
        )

        self._score_composition_remove_options = {
            f"{name or 'unnamed track'} (track {index})": index
            for index, name in zip(control.selected_track_indices, control.selected_track_names)
            if index in control.removable_track_indices
        }
        self.score_composition_remove_combo.configure(
            values=list(self._score_composition_remove_options)
        )
        if self.score_composition_remove_var.get() not in self._score_composition_remove_options:
            self.score_composition_remove_var.set(
                next(iter(self._score_composition_remove_options), "")
            )
        self.remove_score_composition_track_button.configure(
            state="normal" if self._score_composition_remove_options else "disabled"
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

    def _add_score_composition_track(self) -> None:
        role = self.fretboard_role_var.get().strip().lower()
        if role not in {"bass", "lead", "rhythm"}:
            return
        track_index = self._score_composition_add_options.get(
            self.score_composition_add_var.get()
        )
        if track_index is None:
            return
        try:
            add_score_composition_track(self.project, arrangement=role, track_index=track_index)
        except Exception as exc:
            messagebox.showerror("Song Workspace Score Composition", str(exc), parent=self)
            self._refresh_score_composition_panel()
            return
        self.refresh()

    def _remove_score_composition_track(self) -> None:
        role = self.fretboard_role_var.get().strip().lower()
        if role not in {"bass", "lead", "rhythm"}:
            return
        track_index = self._score_composition_remove_options.get(
            self.score_composition_remove_var.get()
        )
        if track_index is None:
            return
        try:
            remove_score_composition_track(self.project, arrangement=role, track_index=track_index)
        except Exception as exc:
            messagebox.showerror("Song Workspace Score Composition", str(exc), parent=self)
            self._refresh_score_composition_panel()
            return
        self.refresh()
