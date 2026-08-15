from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .chord_fingering_ui import ChordFingeringSongWorkspaceWindow
from .reviewed_chords import load_current_reviewed_chords, set_reviewed_chord_group


class ChordIdentitySongWorkspaceWindow(ChordFingeringSongWorkspaceWindow):
    """Song Workspace with explicit human chord-membership authority."""

    def __init__(self, parent: tk.Misc, project, *, run_callback=None) -> None:
        self._chord_identity_selection_key: tuple[str, int] | None = None
        super().__init__(parent, project, run_callback=run_callback)

    def set_project(self, project) -> None:
        self._chord_identity_selection_key = None
        super().set_project(project)

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Human-reviewed chord identity",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="Chord source event indices").pack(side="left")
        self.chord_event_indices_var = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.chord_event_indices_var, width=58).pack(
            side="left", fill="x", expand=True, padx=(6, 12)
        )
        self.accept_chord_identity_button = ttk.Button(
            row,
            text="Accept Chord Identity",
            command=self._accept_chord_identity,
            state="disabled",
        )
        self.accept_chord_identity_button.pack(side="right")
        self.chord_identity_status_var = tk.StringVar(
            value="Select one Lead or Rhythm event, then explicitly define the source events that belong to its chord."
        )
        ttk.Label(
            box,
            textvariable=self.chord_identity_status_var,
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _choose_arrangement_event(self, selected) -> None:
        super()._choose_arrangement_event(selected)
        self._sync_chord_identity_controls(force_prefill=True)

    def _arrangement_clicked(self, event: tk.Event) -> None:
        super()._arrangement_clicked(event)
        if hasattr(self, "accept_chord_identity_button"):
            self._sync_chord_identity_controls(force_prefill=True)

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "accept_chord_identity_button"):
            self._sync_chord_identity_controls(force_prefill=False)

    def _sync_chord_identity_controls(self, *, force_prefill: bool) -> None:
        item = self._selected_arrangement_event
        if item is None or item.instrument not in {"lead", "rhythm"}:
            self._chord_identity_selection_key = None
            self.accept_chord_identity_button.configure(state="disabled")
            self.chord_event_indices_var.set("")
            self.chord_identity_status_var.set(
                "Select one Lead or Rhythm event. Chord identity review is separate from timing, pitch, fingering, techniques, rights, and package readiness."
            )
            return

        key = (item.instrument, item.event_index)
        changed = key != self._chord_identity_selection_key
        self._chord_identity_selection_key = key
        self.accept_chord_identity_button.configure(state="normal")

        reviewed_group: list[int] | None = None
        stale_layer = False
        try:
            layer = load_current_reviewed_chords(self.project)
            if layer is not None:
                for decision in layer.decisions:
                    if (
                        decision.arrangement == item.instrument
                        and decision.source_track_index == item.part_index
                        and item.event_index in decision.event_indices
                    ):
                        reviewed_group = decision.event_indices
                        break
        except ValueError as exc:
            if "stale" in str(exc).lower():
                # Stale authority is not current authority and must not block explicit
                # re-acceptance. The backend validates the new group against current
                # source identity before replacing the obsolete layer.
                stale_layer = True
            else:
                self.accept_chord_identity_button.configure(state="disabled")
                self.chord_identity_status_var.set(f"Chord identity review unavailable: {exc}")
                return
        except (OSError, IndexError) as exc:
            self.accept_chord_identity_button.configure(state="disabled")
            self.chord_identity_status_var.set(f"Chord identity review unavailable: {exc}")
            return

        if force_prefill or changed or not self.chord_event_indices_var.get().strip():
            if reviewed_group is not None:
                indices = reviewed_group
            else:
                try:
                    candidate = self._current_chord_candidate()
                except (OSError, ValueError, IndexError):
                    candidate = None
                indices = candidate.event_indices if candidate is not None else [item.event_index]
            self.chord_event_indices_var.set(", ".join(str(index) for index in indices))

        if stale_layer:
            self.chord_identity_status_var.set(
                "Previous chord review is stale for the current score/fan-out. Define the current source-event group and Accept Chord Identity to replace obsolete authority."
            )
        elif reviewed_group is not None:
            self.chord_identity_status_var.set(
                "This selected event already belongs to a current human-reviewed chord group. Editing and accepting replaces overlapping reviewed membership."
            )
        else:
            self.chord_identity_status_var.set(
                "Automatic simultaneity is only a suggestion. Enter at least two source event indices including the selected event, then explicitly accept the group."
            )

    def _accept_chord_identity(self) -> None:
        item = self._selected_arrangement_event
        if item is None or item.instrument not in {"lead", "rhythm"}:
            return
        try:
            parts = [part.strip() for part in self.chord_event_indices_var.get().split(",")]
            indices = [int(part) for part in parts if part]
            if item.event_index not in indices:
                raise ValueError("reviewed chord must include the currently selected event")
            set_reviewed_chord_group(
                self.project,
                arrangement=item.instrument,
                event_indices=indices,
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Chord Identity Review", str(exc), parent=self)
            return

        self.chord_identity_status_var.set(
            "Chord identity accepted. Source/fan-out bytes and note timing were not changed; current Lead/Rhythm drafts are stale until regenerated."
        )
        self.refresh()
