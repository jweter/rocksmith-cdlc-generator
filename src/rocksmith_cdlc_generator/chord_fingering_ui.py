from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .arrangement_technique_ui import ArrangementTechniqueSongWorkspaceWindow
from .chord_fingering import (
    ChordFingeringNote,
    accept_chord_fingering,
    chord_candidate_for_event,
)


class ChordFingeringSongWorkspaceWindow(ArrangementTechniqueSongWorkspaceWindow):
    """Song Workspace with atomic acceptance of simultaneous guitar fingering."""

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Human-reviewed chord fingering",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))
        self.chord_fingering_status_var = tk.StringVar(
            value="Select a Lead or Rhythm note that belongs to a simultaneous chord."
        )
        ttk.Label(
            box,
            textvariable=self.chord_fingering_status_var,
            wraplength=1120,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        self.accept_chord_fingering_button = ttk.Button(
            box,
            text="Accept Current Chord Fingering",
            command=self._accept_current_chord_fingering,
            state="disabled",
        )
        self.accept_chord_fingering_button.pack(side="right", padx=(12, 0))

    def _choose_arrangement_event(self, selected) -> None:
        super()._choose_arrangement_event(selected)
        self._sync_chord_fingering_controls()

    def _arrangement_clicked(self, event: tk.Event) -> None:
        super()._arrangement_clicked(event)
        if hasattr(self, "accept_chord_fingering_button"):
            self._sync_chord_fingering_controls()

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "accept_chord_fingering_button"):
            self._sync_chord_fingering_controls()

    def _current_chord_candidate(self):
        item = self._selected_arrangement_event
        preview = self.score_preview
        if item is None or preview is None or item.instrument not in {"lead", "rhythm"}:
            return None
        return chord_candidate_for_event(
            preview,
            arrangement=item.instrument,
            event_index=item.event_index,
        )

    def _sync_chord_fingering_controls(self) -> None:
        self.accept_chord_fingering_button.configure(state="disabled")
        try:
            candidate = self._current_chord_candidate()
        except (ValueError, IndexError) as exc:
            self.chord_fingering_status_var.set(f"Chord fingering unavailable: {exc}")
            return
        if candidate is None:
            self.chord_fingering_status_var.set(
                "Select a Lead or Rhythm note that belongs to a simultaneous chord."
            )
            return
        lane = next(
            item for item in self.score_preview.arrangements if item.instrument == candidate.arrangement
        )
        notes = [
            item for item in lane.notes if item.event_index in set(candidate.event_indices)
        ]
        unresolved = [item.event_index for item in notes if item.string_index is None or item.fret is None]
        if unresolved:
            self.chord_fingering_status_var.set(
                "Chord events "
                + ", ".join(str(index) for index in candidate.event_indices)
                + "; resolve each note's string/fret first using Accept Position."
            )
            return
        shape = ", ".join(
            f"event {item.event_index}: s{item.string_index + 1}/f{item.fret}"
            for item in sorted(notes, key=lambda item: item.event_index)
        )
        self.chord_fingering_status_var.set(
            f"{candidate.arrangement.title()} chord at {candidate.start_seconds:.3f}s · {shape}"
        )
        self.accept_chord_fingering_button.configure(state="normal")

    def _accept_current_chord_fingering(self) -> None:
        candidate = self._current_chord_candidate()
        if candidate is None or self.score_preview is None:
            return
        lane = next(
            item for item in self.score_preview.arrangements if item.instrument == candidate.arrangement
        )
        notes = [
            item for item in lane.notes if item.event_index in set(candidate.event_indices)
        ]
        if any(item.string_index is None or item.fret is None for item in notes):
            messagebox.showerror(
                "Chord Fingering Review",
                "Resolve every chord note's string/fret position before accepting the whole fingering.",
                parent=self,
            )
            return
        try:
            accept_chord_fingering(
                self.project,
                arrangement=candidate.arrangement,
                notes=[
                    ChordFingeringNote(
                        event_index=item.event_index,
                        string_index=item.string_index,
                        fret=item.fret,
                    )
                    for item in notes
                    if item.string_index is not None and item.fret is not None
                ],
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Chord Fingering Review", str(exc), parent=self)
            return
        self.chord_fingering_status_var.set(
            "Chord fingering accepted atomically in the existing reviewed-position authority; imported score/fan-out bytes were not changed."
        )
        self.refresh()
