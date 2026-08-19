from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .score_role_composition_workspace_controls import (
    OVERLAP_RESOLUTION_CHOICES,
    ScoreRoleCompositionWorkspaceControl,
    add_score_composition_track,
    build_score_role_composition_workspace_controls,
    compose_role_composition_from_workspace,
    remove_score_composition_track,
    resolve_score_composition_overlaps_from_workspace,
)


class ScoreRoleCompositionWorkspaceMixin:
    """Add multi-track composition status, a track picker, and compose/overlap actions.

    This mirrors ``TrackTrustWorkspaceMixin``: it reuses the existing arrangement role
    selector as the authority for which role the panel describes and never mutates
    project data outside four explicit actions: adding an available score track to a
    role's selection, removing a previously added (non-primary) track, composing the
    role's currently selected tracks when zero cross-track overlaps remain, and
    resolving every currently reported overlap with an explicit human decision before
    composing. Every overlap decision widget offers only the same explicit
    keep_both/keep_left/keep_right choices the CLI's `compose --decisions` accepts;
    nothing here ever infers, defaults, or silently picks a resolution.
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
                "primary track can never be removed here."
            ),
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        overlap_box = ttk.LabelFrame(box, text="Resolve Cross-Track Overlaps", padding=8)
        overlap_box.pack(fill="x", pady=(10, 0))

        self.score_composition_overlap_progress_var = tk.StringVar(value="")
        ttk.Label(
            overlap_box,
            textvariable=self.score_composition_overlap_progress_var,
            wraplength=1020,
            justify="left",
        ).pack(anchor="w")

        overlap_pick_row = ttk.Frame(overlap_box)
        overlap_pick_row.pack(fill="x", pady=(6, 0))
        ttk.Label(overlap_pick_row, text="Overlap:").pack(side="left")
        self.score_composition_overlap_var = tk.StringVar(value="")
        self.score_composition_overlap_combo = ttk.Combobox(
            overlap_pick_row, textvariable=self.score_composition_overlap_var, state="readonly", width=64
        )
        self.score_composition_overlap_combo.pack(side="left", padx=(6, 12))

        ttk.Label(overlap_pick_row, text="Resolution:").pack(side="left")
        self.score_composition_overlap_resolution_var = tk.StringVar(value="")
        self.score_composition_overlap_resolution_combo = ttk.Combobox(
            overlap_pick_row,
            textvariable=self.score_composition_overlap_resolution_var,
            state="readonly",
            width=14,
            values=list(OVERLAP_RESOLUTION_CHOICES),
        )
        self.score_composition_overlap_resolution_combo.pack(side="left", padx=(6, 12))

        self.record_score_composition_overlap_decision_button = ttk.Button(
            overlap_pick_row,
            text="Record Decision",
            command=self._record_score_composition_overlap_decision,
            state="disabled",
        )
        self.record_score_composition_overlap_decision_button.pack(side="left")

        overlap_submit_row = ttk.Frame(overlap_box)
        overlap_submit_row.pack(fill="x", pady=(6, 0))
        self.resolve_score_composition_overlaps_button = ttk.Button(
            overlap_submit_row,
            text="Compose With Decisions",
            command=self._resolve_score_composition_overlaps,
            state="disabled",
        )
        self.resolve_score_composition_overlaps_button.pack(side="left")

        ttk.Label(
            overlap_box,
            text=(
                "Each reported overlap needs its own explicit keep_both/keep_left/keep_right "
                "choice; nothing is auto-resolved. Composing with decisions is enabled only "
                "once every currently reported overlap for this role has a recorded decision. "
                "Equivalent to `cdlc-score-composition overlaps`/`compose --decisions`."
            ),
            wraplength=1020,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self._score_composition_add_options: dict[str, int] = {}
        self._score_composition_remove_options: dict[str, int] = {}
        self._score_composition_overlap_options: dict[str, int] = {}
        self._score_composition_overlap_decisions: dict[int, str] = {}
        self._score_composition_overlap_signature: tuple | None = None

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
        self._reset_score_composition_overlap_picker()

    def _reset_score_composition_overlap_picker(self) -> None:
        self._score_composition_overlap_options = {}
        self._score_composition_overlap_decisions = {}
        self._score_composition_overlap_signature = None
        self.score_composition_overlap_combo.configure(values=[])
        self.score_composition_overlap_var.set("")
        self.score_composition_overlap_resolution_var.set("")
        self.record_score_composition_overlap_decision_button.configure(state="disabled")
        self.resolve_score_composition_overlaps_button.configure(state="disabled")
        self.score_composition_overlap_progress_var.set("")

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

        self._refresh_score_composition_overlap_picker(control)

    def _refresh_score_composition_overlap_picker(
        self, control: ScoreRoleCompositionWorkspaceControl
    ) -> None:
        # A signature over the exact current overlap evidence (not just its count) so a
        # decision recorded against one overlap is never silently kept and reapplied to
        # a different overlap after the underlying selection/track set changes.
        signature = tuple(
            (
                option.index,
                option.overlap.kind,
                option.overlap.left.source_track_index,
                option.overlap.left.event_index,
                option.overlap.right.source_track_index,
                option.overlap.right.event_index,
            )
            for option in control.overlaps
        )
        if signature != self._score_composition_overlap_signature:
            self._score_composition_overlap_decisions = {}
            self._score_composition_overlap_signature = signature

        self._score_composition_overlap_options = {
            option.label: option.index for option in control.overlaps
        }
        self.score_composition_overlap_combo.configure(
            values=list(self._score_composition_overlap_options)
        )
        if self.score_composition_overlap_var.get() not in self._score_composition_overlap_options:
            self.score_composition_overlap_var.set(
                next(iter(self._score_composition_overlap_options), "")
            )
        self.record_score_composition_overlap_decision_button.configure(
            state="normal" if control.overlaps else "disabled"
        )

        total = len(control.overlaps)
        decided = len(self._score_composition_overlap_decisions)
        self.score_composition_overlap_progress_var.set(
            f"{decided} of {total} overlap(s) decided." if total else ""
        )
        self.resolve_score_composition_overlaps_button.configure(
            state="normal" if total and decided == total else "disabled"
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

    def _record_score_composition_overlap_decision(self) -> None:
        overlap_index = self._score_composition_overlap_options.get(
            self.score_composition_overlap_var.get()
        )
        resolution = self.score_composition_overlap_resolution_var.get().strip()
        if overlap_index is None or resolution not in OVERLAP_RESOLUTION_CHOICES:
            # Both an overlap and one of the explicit offered resolutions must be picked;
            # never record a decision from a blank/partial selection.
            return
        self._score_composition_overlap_decisions[overlap_index] = resolution
        self._refresh_score_composition_panel()

    def _resolve_score_composition_overlaps(self) -> None:
        role = self.fretboard_role_var.get().strip().lower()
        if role not in {"bass", "lead", "rhythm"}:
            return
        try:
            resolve_score_composition_overlaps_from_workspace(
                self.project,
                arrangement=role,
                resolutions=dict(self._score_composition_overlap_decisions),
            )
        except Exception as exc:
            messagebox.showerror("Song Workspace Score Composition", str(exc), parent=self)
            self._refresh_score_composition_panel()
            return
        self._score_composition_overlap_decisions = {}
        self.refresh()
