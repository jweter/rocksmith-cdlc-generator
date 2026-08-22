from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .design_tokens import format_status, status_style
from .track_trust_workspace_controls import (
    TrackTrustWorkspaceControl,
    accept_track_source_from_workspace,
    build_track_trust_workspace_controls,
)


class TrackTrustWorkspaceMixin:
    """Add explicit whole-track source-trust review to the final Song Workspace."""

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()

        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Human-reviewed source track trust",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))

        row = ttk.Frame(box)
        row.pack(fill="x")
        self.track_trust_status_var = tk.StringVar(
            value="Track trust status becomes available after score fan-out."
        )
        # #305: this label's foreground is recolored on every _refresh_track_trust_panel
        # call to the shared semantic status palette; the symbol+label text itself, not
        # color, is what always carries the state (never color-alone).
        self.track_trust_status_label = ttk.Label(
            row,
            textvariable=self.track_trust_status_var,
            wraplength=820,
            justify="left",
        )
        self.track_trust_status_label.pack(side="left", fill="x", expand=True)
        self.accept_track_trust_button = ttk.Button(
            row,
            text="Accept Track Source",
            command=self._accept_track_source_trust,
            state="disabled",
        )
        self.accept_track_trust_button.pack(side="right", padx=(12, 0))

        self.track_trust_blocker_var = tk.StringVar(value="")
        ttk.Label(
            box,
            textvariable=self.track_trust_blocker_var,
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            box,
            text=(
                "Acceptance covers only the current imported track's note identity and explicit "
                "string/fret positions. Timing, techniques/ties, chord identity/fingering, validation, "
                "tones, package readiness, mapping, and source rights remain separate human gates."
            ),
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        # The existing arrangement role selector is the authority for which track the
        # panel describes. Refreshing the panel on role changes does not mutate project data.
        self.fretboard_role_var.trace_add("write", self._track_trust_role_changed)

    def refresh(self) -> None:
        super().refresh()
        self._refresh_track_trust_panel()

    def _track_trust_role_changed(self, *_args) -> None:
        if hasattr(self, "track_trust_status_var"):
            self._refresh_track_trust_panel()

    def _selected_track_trust_control(self) -> TrackTrustWorkspaceControl | None:
        role = self.fretboard_role_var.get().strip().lower()
        if role not in {"bass", "lead", "rhythm"}:
            return None
        controls = build_track_trust_workspace_controls(self.project)
        return controls.control_for(role)

    def _reset_track_trust_status_style(self) -> None:
        # Not-yet-actionable states (no project context, no role selected, or a load
        # error) are not one of the semantic pass/stale/review_required states, so fall
        # back to the ttk default label color rather than implying a false status.
        if hasattr(self, "track_trust_status_label"):
            self.track_trust_status_label.configure(foreground="")

    def _refresh_track_trust_panel(self) -> None:
        if not hasattr(self, "track_trust_status_var"):
            return
        try:
            control = self._selected_track_trust_control()
        except Exception as exc:
            self.track_trust_status_var.set(f"Track trust status unavailable: {exc}")
            self.track_trust_blocker_var.set("")
            self.accept_track_trust_button.configure(
                text="Accept Track Source",
                state="disabled",
            )
            self._reset_track_trust_status_style()
            return

        if control is None:
            self.track_trust_status_var.set(
                "Select a Bass, Lead, or Rhythm arrangement to review its source track."
            )
            self.track_trust_blocker_var.set("")
            self.accept_track_trust_button.configure(
                text="Accept Track Source",
                state="disabled",
            )
            self._reset_track_trust_status_style()
            return

        label = control.arrangement.title()
        track_name = control.source_track_name or f"track {control.source_track_index}"
        self.track_trust_status_var.set(
            f"{label} · {track_name} · {control.note_count} notes · {control.status_text}"
        )
        self.track_trust_blocker_var.set(control.blocker_text or "")
        self.accept_track_trust_button.configure(
            text=control.button_text,
            state="normal" if control.button_enabled else "disabled",
        )
        # #305: recolor the status label to the shared semantic palette (foreground is a
        # reinforcing channel only -- control.status_text already carries the symbol and
        # label text via design_tokens.format_status, so this never becomes color-alone).
        if hasattr(self, "track_trust_status_label"):
            self.track_trust_status_label.configure(
                foreground=status_style(control.status_state).foreground
            )

    def _accept_track_source_trust(self) -> None:
        role = self.fretboard_role_var.get().strip().lower()
        if role not in {"bass", "lead", "rhythm"}:
            return
        try:
            controls = accept_track_source_from_workspace(self.project, arrangement=role)
            control = controls.control_for(role)
        except Exception as exc:
            messagebox.showerror("Song Workspace Track Trust", str(exc), parent=self)
            self._refresh_track_trust_panel()
            return

        # Reload the preview so #274's read-only trust projection can immediately
        # reflect current human provenance while preserving independent review flags.
        # refresh() -> _refresh_track_trust_panel() already recolors the label to the
        # "pass" semantic style for the just-accepted control; this only replaces the
        # text with an explicit one-time confirmation, still through format_status so
        # the text keeps carrying the symbol+label the just-applied color reinforces.
        self.refresh()
        if control is not None:
            self.track_trust_status_var.set(
                format_status(
                    "pass",
                    f"{control.arrangement.title()} source track accepted for "
                    f"{control.acceptance_scope.replace('_', ' ')}.",
                )
            )
