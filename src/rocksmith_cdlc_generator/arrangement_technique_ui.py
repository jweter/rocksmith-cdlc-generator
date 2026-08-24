from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .arrangement_event_timing_ui import ArrangementEventTimingSongWorkspaceWindow
from .reviewed_techniques import (
    SUPPORTED_TECHNIQUES,
    load_current_reviewed_techniques,
    set_reviewed_techniques,
)


class ArrangementTechniqueSongWorkspaceWindow(ArrangementEventTimingSongWorkspaceWindow):
    """Direct arrangement selection with explicit human technique acceptance."""

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Human-reviewed techniques",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="Techniques (comma-separated)").pack(side="left")
        self.event_techniques_var = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.event_techniques_var, width=68).pack(
            side="left", fill="x", expand=True, padx=(5, 14)
        )
        self.accept_techniques_button = ttk.Button(
            row,
            text="Accept Techniques",
            command=self._accept_techniques,
            state="disabled",
        )
        self.accept_techniques_button.pack(side="right")
        self.technique_status_var = tk.StringVar(
            value="Select one exact arrangement event. Technique acceptance is separate from timing, position, pitch, rights, and package readiness."
        )
        ttk.Label(
            box,
            textvariable=self.technique_status_var,
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            box,
            text="Supported: " + ", ".join(SUPPORTED_TECHNIQUES),
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))

    def _choose_arrangement_event(self, selected) -> None:
        super()._choose_arrangement_event(selected)
        self._sync_technique_controls()

    def _arrangement_clicked(self, event: tk.Event) -> None:
        super()._arrangement_clicked(event)
        if hasattr(self, "accept_techniques_button"):
            self._sync_technique_controls()

    def _move_review(self, delta: int) -> None:
        super()._move_review(delta)
        if hasattr(self, "accept_techniques_button"):
            self._sync_technique_controls()

    def refresh(self) -> None:
        super().refresh()
        if getattr(self, "_refresh_failed", False):
            return
        if hasattr(self, "accept_techniques_button"):
            self._sync_technique_controls()

    def _sync_technique_controls(self) -> None:
        item = self._selected_arrangement_event
        if item is None:
            self.accept_techniques_button.configure(state="disabled")
            self.event_techniques_var.set("")
            self.technique_status_var.set(
                "Select one exact arrangement event. No technique authority is granted without explicit acceptance."
            )
            return
        self.accept_techniques_button.configure(state="normal")
        self.event_techniques_var.set(", ".join(item.techniques))
        try:
            layer = load_current_reviewed_techniques(self.project)
            reviewed = (
                layer is not None
                and layer.decision_for(item.instrument, item.part_index, item.event_index) is not None
            )
        except ValueError as exc:
            if "stale" in str(exc).lower():
                self.technique_status_var.set(
                    "Previous technique review is stale for the current score. Select this event and Accept Techniques to establish new current authority."
                )
                return
            self.technique_status_var.set(f"Technique review unavailable: {exc}")
            self.accept_techniques_button.configure(state="disabled")
            return
        except Exception as exc:
            self.technique_status_var.set(f"Technique review unavailable: {exc}")
            self.accept_techniques_button.configure(state="disabled")
            return
        self.technique_status_var.set(
            "This event already has current human-reviewed techniques; accepting again replaces that technique set."
            if reviewed
            else "Direct selection grants no technique authority. Edit the list only if needed, then explicitly accept."
        )

    def _accept_techniques(self) -> None:
        item = self._selected_arrangement_event
        if item is None:
            self.technique_status_var.set(
                "No event is selected. Select one exact event before accepting techniques."
            )
            self.accept_techniques_button.configure(state="disabled")
            self.event_techniques_var.set("")
            return
        techniques = [part.strip() for part in self.event_techniques_var.get().split(",") if part.strip()]
        try:
            set_reviewed_techniques(
                self.project,
                arrangement=item.instrument,
                event_index=item.event_index,
                techniques=techniques,
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Technique Review", str(exc), parent=self)
            return

        self.technique_status_var.set(
            "Techniques accepted. Imported score/fan-out bytes were not changed; current Lead/Rhythm drafts are stale until regenerated."
        )
        identity = (item.instrument, item.event_index)
        self.refresh()
        if self.score_preview is not None:
            arrangement = next(
                (candidate for candidate in self.score_preview.arrangements if candidate.instrument == identity[0]),
                None,
            )
            if arrangement is not None:
                note = next((candidate for candidate in arrangement.notes if candidate.event_index == identity[1]), None)
                if note is not None:
                    self._seek_to(note.start_seconds)
