from __future__ import annotations

import tkinter as tk

from .arrangement_event_selection import (
    SelectedArrangementEvent,
    locate_arrangement_events,
)
from .arrangement_preview_ui import ArrangementPreviewSongWorkspaceWindow
from .reviewed_positions import load_current_reviewed_positions
from .song_preview import PreviewReviewItem


class ArrangementEventSelectionSongWorkspaceWindow(ArrangementPreviewSongWorkspaceWindow):
    """Arrangement preview with direct selection of any visible source event."""

    def __init__(self, parent: tk.Misc, project, *, run_callback=None) -> None:
        self._selected_arrangement_event: SelectedArrangementEvent | None = None
        self._candidate_menu: tk.Menu | None = None
        super().__init__(parent, project, run_callback=run_callback)

    def set_project(self, project) -> None:
        self._selected_arrangement_event = None
        super().set_project(project)

    def refresh(self) -> None:
        selected_identity = None
        if self._selected_arrangement_event is not None:
            selected_identity = (
                self._selected_arrangement_event.instrument,
                self._selected_arrangement_event.event_index,
            )
        super().refresh()
        if selected_identity is None or self.score_preview is None:
            return
        instrument, event_index = selected_identity
        arrangement = next(
            (item for item in self.score_preview.arrangements if item.instrument == instrument),
            None,
        )
        if arrangement is None:
            self._selected_arrangement_event = None
            return
        note = next((item for item in arrangement.notes if item.event_index == event_index), None)
        if note is None:
            self._selected_arrangement_event = None
            return
        self._selected_arrangement_event = SelectedArrangementEvent(
            instrument=arrangement.instrument,
            part_index=arrangement.part_index,
            part_name=arrangement.part_name,
            event_index=note.event_index,
            start_seconds=note.start_seconds,
            duration_seconds=note.duration_seconds,
            midi=note.midi,
            note_name=note.note_name,
            string_index=note.string_index,
            fret=note.fret,
            techniques=list(note.techniques),
            import_confidence=note.import_confidence,
            trust_class=note.trust_class,
            review_required=note.review_required,
        )
        self._show_selected_arrangement_event()

    def _arrangement_clicked(self, event: tk.Event) -> None:
        preview = self.score_preview
        if preview is None or self.snapshot is None:
            return

        canvas = self.arrangement_canvas
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 220)
        lanes = preview.arrangements
        if not lanes:
            return

        margin = 70.0
        usable = max(width - 2 * margin, 1.0)
        start, end = self._view_bounds()
        fraction = min(max((float(event.x) - margin) / usable, 0.0), 1.0)
        clicked_time = start + fraction * (end - start)

        lane_height = max((height - 35) / len(lanes), 45)
        lane_index = int((float(event.y) - 20.0) // lane_height)
        if lane_index < 0 or lane_index >= len(lanes):
            self._selected_arrangement_event = None
            self._seek_to(clicked_time)
            return
        y0 = 20.0 + lane_index * lane_height
        y1 = y0 + lane_height - 8.0
        if float(event.y) < y0 or float(event.y) > y1:
            self._selected_arrangement_event = None
            self._seek_to(clicked_time)
            return

        # Six pixels of horizontal hit tolerance keeps very short notes selectable while
        # remaining proportional to the current zoom window.
        tolerance = max((end - start) * 6.0 / usable, 0.002)
        selection = locate_arrangement_events(
            preview,
            lane_index=lane_index,
            time_seconds=clicked_time,
            tolerance_seconds=tolerance,
        )
        if not selection.candidates:
            self._selected_arrangement_event = None
            self._seek_to(clicked_time)
            self.preview_detail_var.set(
                "No arrangement event at this location. The playhead moved without changing chart data."
            )
            self.accept_position_button.configure(state="disabled")
            self._draw_arrangement_preview()
            return

        if selection.requires_choice:
            self._selected_arrangement_event = None
            self._preview_review_index = None
            self._seek_to(clicked_time)
            self.accept_position_button.configure(state="disabled")
            self.preview_detail_var.set(
                f"{len(selection.candidates)} notes overlap here. Choose the specific note; no musical authority has been granted."
            )
            self._show_candidate_menu(event, selection.candidates)
            self._draw_arrangement_preview()
            return

        self._choose_arrangement_event(selection.candidates[0])

    def _show_candidate_menu(
        self,
        event: tk.Event,
        candidates: list[SelectedArrangementEvent],
    ) -> None:
        if self._candidate_menu is not None:
            try:
                self._candidate_menu.destroy()
            except tk.TclError:
                pass
        menu = tk.Menu(self, tearoff=False)
        self._candidate_menu = menu
        for candidate in candidates:
            physical = (
                f"string {candidate.string_index + 1}, fret {candidate.fret}"
                if candidate.string_index is not None and candidate.fret is not None
                else "position unresolved"
            )
            label = f"{candidate.note_name or candidate.midi} · event {candidate.event_index} · {physical}"
            menu.add_command(
                label=label,
                command=lambda item=candidate: self._choose_arrangement_event(item),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _choose_arrangement_event(self, selected: SelectedArrangementEvent) -> None:
        self._selected_arrangement_event = selected
        self._preview_review_index = None
        self._seek_to(selected.start_seconds)
        self._show_selected_arrangement_event()

    def _show_selected_arrangement_event(self) -> None:
        item = self._selected_arrangement_event
        if item is None:
            return
        self.fretboard_role_var.set(item.instrument)
        physical = (
            f"string {item.string_index + 1}, fret {item.fret}"
            if item.string_index is not None and item.fret is not None
            else "physical position unresolved"
        )
        techniques = ", ".join(item.techniques) if item.techniques else "none"
        review_state = "review required" if item.review_required else "not currently flagged"
        self.preview_detail_var.set(
            f"Selected · {item.instrument.title()} event {item.event_index} · "
            f"{item.start_seconds:.3f}s recording time · {item.note_name or item.midi} · {physical}\n"
            f"confidence {item.import_confidence:.2f} · trust {item.trust_class.value} · "
            f"{review_state} · techniques: {techniques}"
        )
        self.position_string_var.set(
            str(item.string_index + 1) if item.string_index is not None else ""
        )
        self.position_fret_var.set(str(item.fret) if item.fret is not None else "")
        self.accept_position_button.configure(state="normal")

        try:
            layer = load_current_reviewed_positions(self.project)
            reviewed = (
                layer is not None
                and layer.decision_for(item.instrument, item.part_index, item.event_index) is not None
            )
        except Exception:
            reviewed = False
        self.position_status_var.set(
            "This event already has a current human-reviewed position; accepting again replaces that decision."
            if reviewed
            else "Direct lane selection does not grant authority. Accept Position is still the explicit human decision."
        )
        self._draw_arrangement_preview()
        self._draw_fretboard()

    def _current_review_item(self) -> PreviewReviewItem | None:
        item = self._selected_arrangement_event
        if item is None:
            return super()._current_review_item()
        return PreviewReviewItem(
            review_id=f"selected:{item.instrument}:{item.part_index}:{item.event_index}",
            instrument=item.instrument,
            part_name=item.part_name,
            event_index=item.event_index,
            start_seconds=item.start_seconds,
            duration_seconds=item.duration_seconds,
            midi=item.midi,
            note_name=item.note_name,
            string_index=item.string_index,
            fret=item.fret,
            techniques=list(item.techniques),
            import_confidence=item.import_confidence,
            trust_class=item.trust_class,
        )

    def _move_review(self, delta: int) -> None:
        self._selected_arrangement_event = None
        super()._move_review(delta)

    def _draw_arrangement_preview(self) -> None:
        super()._draw_arrangement_preview()
        selected = self._selected_arrangement_event
        preview = self.score_preview
        if selected is None or preview is None or self.snapshot is None:
            return

        arrangement_index = next(
            (
                index
                for index, arrangement in enumerate(preview.arrangements)
                if arrangement.instrument == selected.instrument
            ),
            None,
        )
        if arrangement_index is None:
            return
        arrangement = preview.arrangements[arrangement_index]
        note = next(
            (item for item in arrangement.notes if item.event_index == selected.event_index),
            None,
        )
        if note is None:
            return

        start, end = self._view_bounds()
        if note.end_seconds < start or note.start_seconds > end:
            return
        canvas = self.arrangement_canvas
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 220)
        lane_height = max((height - 35) / max(len(preview.arrangements), 1), 45)
        y0 = 20 + arrangement_index * lane_height
        y1 = y0 + lane_height - 8
        x1 = self._preview_x(max(note.start_seconds, start), width)
        x2 = self._preview_x(min(note.end_seconds, end), width)
        if x2 - x1 < 5:
            x2 = x1 + 5
        canvas.create_rectangle(x1 - 2, y0 + 4, x2 + 2, y1 - 4, width=3, dash=(4, 2))
