from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .arrangement_event_selection_ui import ArrangementEventSelectionSongWorkspaceWindow
from .reviewed_event_timing import load_current_reviewed_event_timing, set_reviewed_event_timing


class ArrangementEventTimingSongWorkspaceWindow(ArrangementEventSelectionSongWorkspaceWindow):
    """Direct arrangement selection with explicit onset/duration acceptance."""

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Human-reviewed event timing",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="Start (recording seconds)").pack(side="left")
        self.event_start_var = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.event_start_var, width=12).pack(side="left", padx=(5, 14))
        ttk.Label(row, text="Duration (seconds)").pack(side="left")
        self.event_duration_var = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.event_duration_var, width=12).pack(side="left", padx=(5, 14))
        self.accept_event_timing_button = ttk.Button(
            row,
            text="Accept Event Timing",
            command=self._accept_event_timing,
            state="disabled",
        )
        self.accept_event_timing_button.pack(side="right")
        self.event_timing_status_var = tk.StringVar(
            value="Select one exact arrangement event. Timing acceptance is explicit and separate from position, pitch, techniques, rights, and package readiness."
        )
        ttk.Label(
            box,
            textvariable=self.event_timing_status_var,
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _choose_arrangement_event(self, selected) -> None:
        super()._choose_arrangement_event(selected)
        self._sync_event_timing_controls()

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "accept_event_timing_button"):
            self._sync_event_timing_controls()

    def _sync_event_timing_controls(self) -> None:
        item = self._selected_arrangement_event
        if item is None:
            self.accept_event_timing_button.configure(state="disabled")
            self.event_start_var.set("")
            self.event_duration_var.set("")
            return
        self.accept_event_timing_button.configure(state="normal")
        self.event_start_var.set(f"{item.start_seconds:.6f}")
        self.event_duration_var.set(f"{item.duration_seconds:.6f}")
        try:
            layer = load_current_reviewed_event_timing(self.project)
            reviewed = (
                layer is not None
                and layer.decision_for(item.instrument, item.part_index, item.event_index) is not None
            )
        except Exception as exc:
            self.event_timing_status_var.set(f"Timing review unavailable: {exc}")
            self.accept_event_timing_button.configure(state="disabled")
            return
        self.event_timing_status_var.set(
            "This event already has current human-reviewed timing; accepting again replaces that decision."
            if reviewed
            else "Direct selection grants no timing authority. Change the fields only if needed, then explicitly accept."
        )

    def _accept_event_timing(self) -> None:
        item = self._selected_arrangement_event
        if item is None:
            return
        try:
            start = float(self.event_start_var.get())
            duration = float(self.event_duration_var.get())
            set_reviewed_event_timing(
                self.project,
                arrangement=item.instrument,
                event_index=item.event_index,
                start_seconds=start,
                duration_seconds=duration,
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Event Timing Review", str(exc), parent=self)
            return

        self.event_timing_status_var.set(
            "Timing accepted. Imported score/fan-out and shared timing were not changed; current Lead/Rhythm drafts are stale until regenerated."
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
