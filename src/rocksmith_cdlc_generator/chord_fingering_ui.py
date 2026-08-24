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
            value="Select a Lead or Rhythm note that belongs to a simultaneous source chord."
        )
        ttk.Label(
            box,
            textvariable=self.chord_fingering_status_var,
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", fill="x")
        self.chord_positions_frame = ttk.Frame(box)
        self.chord_positions_frame.pack(fill="x", pady=(7, 0))
        self._chord_position_vars: dict[int, tuple[tk.StringVar, tk.StringVar]] = {}
        self.accept_chord_fingering_button = ttk.Button(
            box,
            text="Accept Current Chord Fingering",
            command=self._accept_current_chord_fingering,
            state="disabled",
        )
        self.accept_chord_fingering_button.pack(anchor="e", pady=(7, 0))

    def _choose_arrangement_event(self, selected) -> None:
        super()._choose_arrangement_event(selected)
        self._sync_chord_fingering_controls()

    def _arrangement_clicked(self, event: tk.Event) -> None:
        super()._arrangement_clicked(event)
        if hasattr(self, "accept_chord_fingering_button"):
            self._sync_chord_fingering_controls()

    def refresh(self) -> None:
        super().refresh()
        if getattr(self, "_refresh_failed", False):
            return
        if hasattr(self, "accept_chord_fingering_button"):
            self._sync_chord_fingering_controls()

    def _current_chord_candidate(self):
        item = self._selected_arrangement_event
        preview = self.score_preview
        if item is None or preview is None or item.instrument not in {"lead", "rhythm"}:
            return None
        return chord_candidate_for_event(
            self.project,
            preview,
            arrangement=item.instrument,
            event_index=item.event_index,
        )

    def _clear_chord_position_rows(self) -> None:
        for child in self.chord_positions_frame.winfo_children():
            child.destroy()
        self._chord_position_vars = {}

    def _sync_chord_fingering_controls(self) -> None:
        self.accept_chord_fingering_button.configure(state="disabled")
        self._clear_chord_position_rows()
        try:
            candidate = self._current_chord_candidate()
        except (OSError, ValueError, IndexError) as exc:
            self.chord_fingering_status_var.set(f"Chord fingering unavailable: {exc}")
            return
        if candidate is None:
            self.chord_fingering_status_var.set(
                "Select a Lead or Rhythm note that belongs to a simultaneous source chord."
            )
            return
        lane = next(
            item for item in self.score_preview.arrangements if item.instrument == candidate.arrangement
        )
        by_index = {item.event_index: item for item in lane.notes}
        notes = [by_index[index] for index in candidate.event_indices]

        ttk.Label(self.chord_positions_frame, text="Event / pitch", width=20).grid(row=0, column=0, sticky="w")
        ttk.Label(self.chord_positions_frame, text="String (1-based)", width=18).grid(row=0, column=1, sticky="w")
        ttk.Label(self.chord_positions_frame, text="Fret", width=10).grid(row=0, column=2, sticky="w")
        for row_index, note in enumerate(notes, start=1):
            ttk.Label(
                self.chord_positions_frame,
                text=f"event {note.event_index} · {note.note_name or note.midi}",
                width=20,
            ).grid(row=row_index, column=0, sticky="w", pady=2)
            string_var = tk.StringVar(
                value=str(note.string_index + 1) if note.string_index is not None else ""
            )
            fret_var = tk.StringVar(value=str(note.fret) if note.fret is not None else "")
            ttk.Spinbox(
                self.chord_positions_frame,
                from_=1,
                to=8,
                width=7,
                textvariable=string_var,
            ).grid(row=row_index, column=1, sticky="w", pady=2)
            ttk.Spinbox(
                self.chord_positions_frame,
                from_=0,
                to=36,
                width=7,
                textvariable=fret_var,
            ).grid(row=row_index, column=2, sticky="w", pady=2)
            self._chord_position_vars[note.event_index] = (string_var, fret_var)

        self.chord_fingering_status_var.set(
            f"{candidate.arrangement.title()} source chord · events "
            + ", ".join(str(index) for index in candidate.event_indices)
            + ". Edit every tone here; no position authority is written until the whole chord is accepted atomically."
        )
        self.accept_chord_fingering_button.configure(state="normal")

    def _draft_chord_fingering_notes(self, candidate) -> list[ChordFingeringNote]:
        notes: list[ChordFingeringNote] = []
        for event_index in candidate.event_indices:
            variables = self._chord_position_vars.get(event_index)
            if variables is None:
                raise ValueError(f"Missing chord fingering controls for event {event_index}")
            string_raw = variables[0].get().strip()
            fret_raw = variables[1].get().strip()
            if not string_raw or not fret_raw:
                raise ValueError("Enter a string and fret for every chord tone before accepting")
            string_number = int(string_raw)
            fret = int(fret_raw)
            if string_number < 1:
                raise ValueError("Chord string numbers must be 1 or greater")
            notes.append(
                ChordFingeringNote(
                    event_index=event_index,
                    string_index=string_number - 1,
                    fret=fret,
                )
            )
        return notes

    def _accept_current_chord_fingering(self) -> None:
        try:
            candidate = self._current_chord_candidate()
            if candidate is None:
                return
            notes = self._draft_chord_fingering_notes(candidate)
            accept_chord_fingering(
                self.project,
                arrangement=candidate.arrangement,
                notes=notes,
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Chord Fingering Review", str(exc), parent=self)
            return
        self.chord_fingering_status_var.set(
            "Chord fingering accepted atomically in the existing reviewed-position authority; imported score/fan-out bytes were not changed."
        )
        self.refresh()
