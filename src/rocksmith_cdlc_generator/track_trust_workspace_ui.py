from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .desktop_theme import PALETTE, status_dark_foreground
from .track_trust_status_presentation import present_track_trust_status
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

        self.track_trust_status_var = tk.StringVar(
            value="Track trust status becomes available after score fan-out."
        )
        self.track_trust_status_label = ttk.Label(
            box,
            textvariable=self.track_trust_status_var,
            wraplength=1120,
            justify="left",
        )
        self.track_trust_status_label.pack(anchor="w")

        # track_trust_content_frame/track_trust_unavailable_label are mutually exclusive
        # and toggled by _update_track_trust_availability(): the pair is the only content
        # packed into box after the always-visible status label, so pack()/pack_forget()
        # never reorders anything else (issue #563: a score-only project with no
        # arrangement draft otherwise renders a full-width always-disabled Accept button
        # plus two further disclaimer lines even though none of it can ever be actionable).
        self.track_trust_content_frame = ttk.Frame(box)
        self.track_trust_unavailable_label = ttk.Label(
            box,
            text="Track trust review becomes available once score fan-out produces a Bass, Lead, or Rhythm arrangement draft.",
            wraplength=1120,
            justify="left",
            foreground=PALETTE.text_muted,
        )

        row = ttk.Frame(self.track_trust_content_frame)
        row.pack(fill="x")
        self.accept_track_trust_button = ttk.Button(
            row,
            text="Accept Track Source",
            command=self._accept_track_source_trust,
            state="disabled",
        )
        self.accept_track_trust_button.pack(side="right")

        self.track_trust_blocker_var = tk.StringVar(value="")
        ttk.Label(
            self.track_trust_content_frame,
            textvariable=self.track_trust_blocker_var,
            wraplength=1050,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            self.track_trust_content_frame,
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
        self._update_track_trust_availability()

    def _update_track_trust_availability(self) -> None:
        """Show compact status text instead of a full-width always-disabled control.

        ``track_trust_content_frame``/``track_trust_unavailable_label`` are the only
        content packed into ``box`` after the always-visible status label above, so
        toggling which one is packed never reorders anything else (see the construction
        comment in ``_build_arrangement_preview``).
        """

        if not hasattr(self, "track_trust_content_frame"):
            return
        if self.score_preview is not None:
            self.track_trust_unavailable_label.pack_forget()
            self.track_trust_content_frame.pack(fill="x")
        else:
            self.track_trust_content_frame.pack_forget()
            self.track_trust_unavailable_label.pack(fill="x", anchor="w", pady=(6, 0))

    def refresh(self) -> None:
        super().refresh()
        if getattr(self, "_refresh_failed", False):
            return
        self._update_track_trust_availability()
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

    def _set_track_trust_status_foreground(self, status_state: str | None) -> None:
        """Apply (or clear) the shared semantic status color on the status label.

        Only the reinforcing color channel is set here -- the symbol + label text
        that carries the actual meaning is already part of the string
        ``present_track_trust_status`` returns, per the #305 non-color-alone rule.
        Resolved through ``desktop_theme.status_dark_foreground`` (not
        ``design_tokens.status_style(...).foreground``) because this panel renders on
        the packaged app's dark theme, where the light-background status tokens are
        low-contrast to illegible -- the same fix already applied to the Song
        Workspace header health indicator and Review Queue severity column.
        """

        if not hasattr(self, "track_trust_status_label"):
            return
        foreground = status_dark_foreground(status_state) if status_state is not None else ""
        self.track_trust_status_label.configure(foreground=foreground)

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
            self._set_track_trust_status_foreground(None)
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
            self._set_track_trust_status_foreground(None)
            return

        presentation = present_track_trust_status(control)
        self.track_trust_status_var.set(presentation.text)
        self._set_track_trust_status_foreground(presentation.status_state)
        self.track_trust_blocker_var.set(control.blocker_text or "")
        self.accept_track_trust_button.configure(
            text=control.button_text,
            state="normal" if control.button_enabled else "disabled",
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
        self.refresh()
        if control is not None:
            self.track_trust_status_var.set(
                f"{control.arrangement.title()} source track accepted for "
                f"{control.acceptance_scope.replace('_', ' ')}."
            )
