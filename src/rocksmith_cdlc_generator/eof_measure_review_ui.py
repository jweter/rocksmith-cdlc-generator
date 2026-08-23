from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .eof_hand_position_project import load_current_project_eof_hand_position_status
from .eof_measure_review import (
    MeasureWindow,
    build_measure_windows,
    measure_index_for_time,
    notes_for_measure,
    summarize_measure_fingering,
)


class EOFMeasureReviewMixin:
    """EOF-inspired, read-only measure/fingering inspection for Arrangement Preview.

    EOF is a behavioral/reference surface only. This view is computed from the current
    project-owned preview snapshot and never imports EOF edits or records acceptance.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._eof_measure_windows: list[MeasureWindow] = []
        self._eof_measure_index: int | None = None
        self._measure_note_times: dict[str, float] = {}
        super().__init__(*args, **kwargs)

    def set_project(self, project) -> None:
        self._eof_measure_windows = []
        self._eof_measure_index = None
        self._measure_note_times = {}
        super().set_project(project)

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()

        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Measure fingering inspector · EOF-inspired",
            padding=8,
        )
        box.pack(fill="x", pady=(8, 0))

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="◀ Previous bar", command=lambda: self._step_measure(-1)).pack(side="left")
        ttk.Button(toolbar, text="Next bar ▶", command=lambda: self._step_measure(1)).pack(side="left", padx=(6, 0))
        self.eof_measure_follow_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Follow play/seek cursor",
            variable=self.eof_measure_follow_var,
            command=self._refresh_eof_measure_review,
        ).pack(side="left", padx=(14, 0))

        self.eof_measure_status_var = tk.StringVar(
            value="Measure data will appear when authoritative score timing is available."
        )
        ttk.Label(
            toolbar,
            textvariable=self.eof_measure_status_var,
            justify="left",
        ).pack(side="left", fill="x", expand=True, padx=(14, 0))

        self.eof_measure_fret_var = tk.StringVar(value="")
        ttk.Label(
            box,
            textvariable=self.eof_measure_fret_var,
            justify="left",
            wraplength=1050,
        ).pack(fill="x", pady=(6, 5))

        columns = ("offset", "note", "string", "fret", "techniques", "review")
        self.eof_measure_tree = ttk.Treeview(
            box,
            columns=columns,
            show="headings",
            height=7,
            selectmode="browse",
        )
        headings = {
            "offset": "Bar time",
            "note": "Note",
            "string": "String",
            "fret": "Fret",
            "techniques": "Techniques",
            "review": "Review",
        }
        widths = {
            "offset": 90,
            "note": 90,
            "string": 70,
            "fret": 60,
            "techniques": 300,
            "review": 110,
        }
        for column in columns:
            self.eof_measure_tree.heading(column, text=headings[column])
            self.eof_measure_tree.column(column, width=widths[column], anchor="w")
        self.eof_measure_tree.pack(fill="x")
        self.eof_measure_tree.bind("<<TreeviewSelect>>", self._measure_event_selected)

        ttk.Label(
            box,
            text=(
                "Observed positions are project-owned source/review data. The fret span is descriptive, "
                "not an automatically accepted hand position. EOF hand-position observations, when present, "
                "remain advisory evidence only."
            ),
            justify="left",
            wraplength=1050,
        ).pack(fill="x", pady=(6, 0))

        if hasattr(self, "fretboard_role_combo"):
            self.fretboard_role_combo.bind(
                "<<ComboboxSelected>>",
                lambda _event: self._refresh_eof_measure_review(),
                add="+",
            )

    def refresh(self) -> None:
        super().refresh()
        preview = getattr(self, "score_preview", None)
        self._eof_measure_windows = build_measure_windows(preview) if preview is not None else []
        if not self._eof_measure_windows:
            self._eof_measure_index = None
        elif self._eof_measure_index is None or self._eof_measure_index >= len(self._eof_measure_windows):
            when = float(getattr(self, "_selected_time", None) or 0.0)
            self._eof_measure_index = measure_index_for_time(self._eof_measure_windows, when)
        self._refresh_eof_measure_review()

    def _seek_to(self, seconds: float) -> None:
        super()._seek_to(seconds)
        if getattr(self, "eof_measure_follow_var", None) is not None and self.eof_measure_follow_var.get():
            index = measure_index_for_time(self._eof_measure_windows, float(seconds))
            if index is not None and index != self._eof_measure_index:
                self._eof_measure_index = index
                self._refresh_eof_measure_review()

    def _step_measure(self, delta: int) -> None:
        if not self._eof_measure_windows:
            return
        if self._eof_measure_index is None:
            self._eof_measure_index = 0
        else:
            self._eof_measure_index = min(
                max(self._eof_measure_index + delta, 0),
                len(self._eof_measure_windows) - 1,
            )
        measure = self._eof_measure_windows[self._eof_measure_index]
        self._seek_to(measure.start_seconds)
        self._refresh_eof_measure_review()

    def _measure_event_selected(self, _event=None) -> None:
        if not hasattr(self, "eof_measure_tree"):
            return
        selection = self.eof_measure_tree.selection()
        if not selection:
            return
        when = self._measure_note_times.get(selection[0])
        if when is not None:
            self._seek_to(when)

    def _active_measure_arrangement(self):
        preview = getattr(self, "score_preview", None)
        if preview is None:
            return None
        role = self.fretboard_role_var.get() if hasattr(self, "fretboard_role_var") else ""
        return next((item for item in preview.arrangements if item.instrument == role), None)

    def _refresh_eof_measure_review(self) -> None:
        if not hasattr(self, "eof_measure_status_var"):
            return
        if not self._eof_measure_windows:
            self.eof_measure_status_var.set(
                "Measure view unavailable: current preview does not expose authoritative bar/beat timing."
            )
            self.eof_measure_fret_var.set("")
            if hasattr(self, "eof_measure_tree"):
                self.eof_measure_tree.delete(*self.eof_measure_tree.get_children())
            return

        if self.eof_measure_follow_var.get():
            when = float(getattr(self, "_selected_time", None) or 0.0)
            index = measure_index_for_time(self._eof_measure_windows, when)
            if index is not None:
                self._eof_measure_index = index
        if self._eof_measure_index is None:
            self._eof_measure_index = 0

        measure = self._eof_measure_windows[self._eof_measure_index]
        arrangement = self._active_measure_arrangement()
        self.eof_measure_status_var.set(
            f"Bar {measure.number}/{len(self._eof_measure_windows)} · "
            f"{measure.numerator}/{measure.denominator} · "
            f"{measure.start_seconds:.3f}-{measure.end_seconds:.3f}s"
        )
        if arrangement is None:
            self.eof_measure_fret_var.set("Choose an available arrangement to inspect physical positions.")
            return

        summary = summarize_measure_fingering(arrangement, measure)
        strings = ", ".join(str(value) for value in summary.active_strings) or "none"
        evidence_text = ""
        try:
            eof_status = load_current_project_eof_hand_position_status(self.project)
        except (OSError, ValueError):
            eof_status = None
        if eof_status is not None and eof_status.instrument == arrangement.instrument:
            evidence_text = (
                f" · EOF advisory hand-position evidence: {eof_status.evidence.observation_count} markers"
            )
        self.eof_measure_fret_var.set(
            f"{arrangement.instrument.title()} · {summary.event_count} events · "
            f"observed {summary.fret_span_text} · strings {strings} · "
            f"open strings {summary.open_string_count} · unresolved positions "
            f"{summary.unresolved_position_count} · review-required {summary.review_required_count}"
            f"{evidence_text}"
        )

        self.eof_measure_tree.delete(*self.eof_measure_tree.get_children())
        self._measure_note_times = {}
        notes = notes_for_measure(arrangement, measure)
        for note in sorted(
            notes,
            key=lambda item: (
                item.start_seconds,
                item.string_index if item.string_index is not None else 99,
                item.midi,
            ),
        ):
            iid = f"{arrangement.instrument}-{note.event_index}"
            self._measure_note_times[iid] = note.start_seconds
            offset = note.start_seconds - measure.start_seconds
            note_label = note.note_name or f"MIDI {note.midi}"
            string_label = str(note.string_index + 1) if note.string_index is not None else "?"
            fret_label = str(note.fret) if note.fret is not None else "?"
            techniques = ", ".join(note.techniques) if note.techniques else ""
            review = "REVIEW" if note.review_required else ""
            self.eof_measure_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    f"+{offset:.3f}s",
                    note_label,
                    string_label,
                    fret_label,
                    techniques,
                    review,
                ),
            )
