from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from .printed_score_review import (
    PrintedScoreReviewError,
    PrintedScoreReviewRecord,
    ReviewedScoreEvent,
    ReviewedScoreMeasure,
    create_review_draft,
    default_review_path,
    save_review_record,
    write_reviewed_fixture,
)
from .score_measure_recognition import PrintedScoreRecognitionCandidateSet


class PrintedScoreReviewWindow(tk.Toplevel):
    """Human-authority surface for private photographed-score recognition candidates."""

    def __init__(
        self,
        master: tk.Misc,
        project_dir: Path,
        candidate_path: Path,
        *,
        default_bpm: float = 80.0,
    ) -> None:
        super().__init__(master)
        self.project_root = Path(project_dir).expanduser().resolve()
        self.candidate_path = Path(candidate_path).expanduser().resolve()
        self.record = self._load_or_create_record()
        self.candidates = PrintedScoreRecognitionCandidateSet.model_validate_json(
            self.candidate_path.read_text(encoding="utf-8")
        )
        self.measure_position = 0
        self._photo: ImageTk.PhotoImage | None = None
        self._page_image = self._load_private_derivative()

        self.title(f"Printed Score Review — page {self.record.printed_page}")
        self.geometry("1180x820")
        self.minsize(980, 700)

        self.measure_status_var = tk.StringVar()
        self.measure_counter_var = tk.StringVar()
        self.global_status_var = tk.StringVar()
        self.bpm_var = tk.StringVar(value=f"{default_bpm:g}")
        self.kind_var = tk.StringVar(value="note")
        self.beat_var = tk.StringVar()
        self.duration_var = tk.StringVar()
        self.string_var = tk.StringVar()
        self.fret_var = tk.StringVar()
        self.techniques_var = tk.StringVar()
        self.reviewer_note_var = tk.StringVar()

        self._build_layout()
        self._render_measure()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _load_or_create_record(self) -> PrintedScoreReviewRecord:
        draft = create_review_draft(self.project_root, self.candidate_path)
        review_path = default_review_path(self.project_root, draft)
        if review_path.is_file():
            existing = PrintedScoreReviewRecord.read_json(review_path)
            if existing.candidate_sha256 != draft.candidate_sha256:
                raise PrintedScoreReviewError(
                    "saved review belongs to a different recognition candidate file"
                )
            return existing
        return draft

    def _load_private_derivative(self) -> Image.Image:
        derivative = (self.project_root / self.candidates.derivative_relative_path).resolve()
        if not derivative.is_relative_to(self.project_root):
            raise PrintedScoreReviewError("normalized derivative escaped private project")
        if not derivative.is_file():
            raise FileNotFoundError(derivative)
        with Image.open(derivative) as opened:
            return opened.convert("L").copy()

    def _build_layout(self) -> None:
        header = ttk.Frame(self, padding=10)
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Human review is authoritative. Model confidence alone never approves a note.",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        ttk.Label(header, textvariable=self.global_status_var).pack(side="right")

        navigation = ttk.Frame(self, padding=(10, 0, 10, 8))
        navigation.pack(fill="x")
        ttk.Button(navigation, text="◀ Previous", command=self._previous_measure).pack(side="left")
        ttk.Label(navigation, textvariable=self.measure_counter_var).pack(side="left", padx=12)
        ttk.Label(navigation, textvariable=self.measure_status_var).pack(side="left", padx=12)
        ttk.Button(navigation, text="Next ▶", command=self._next_measure).pack(side="left")
        ttk.Button(navigation, text="Approve Measure", command=self._approve_measure).pack(
            side="right"
        )
        ttk.Button(navigation, text="Mark Pending", command=self._mark_pending).pack(
            side="right", padx=(0, 8)
        )

        image_frame = ttk.LabelFrame(self, text="Source measure crop", padding=8)
        image_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.image_label = ttk.Label(image_frame, anchor="center")
        self.image_label.pack(fill="x")

        middle = ttk.Panedwindow(self, orient="horizontal")
        middle.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        event_frame = ttk.LabelFrame(middle, text="Recognized / reviewed events", padding=8)
        edit_frame = ttk.LabelFrame(middle, text="Selected event", padding=8)
        middle.add(event_frame, weight=3)
        middle.add(edit_frame, weight=2)

        columns = ("index", "kind", "beat", "duration", "string", "fret", "techniques", "action")
        self.event_tree = ttk.Treeview(
            event_frame,
            columns=columns,
            show="headings",
            height=10,
            selectmode="browse",
        )
        headings = {
            "index": "#",
            "kind": "Kind",
            "beat": "Beat",
            "duration": "Duration",
            "string": "String",
            "fret": "Fret",
            "techniques": "Techniques",
            "action": "Review action",
        }
        widths = {
            "index": 38,
            "kind": 62,
            "beat": 62,
            "duration": 72,
            "string": 56,
            "fret": 48,
            "techniques": 130,
            "action": 90,
        }
        for column in columns:
            self.event_tree.heading(column, text=headings[column])
            self.event_tree.column(column, width=widths[column], anchor="center")
        self.event_tree.pack(fill="both", expand=True)
        self.event_tree.bind("<<TreeviewSelect>>", self._event_selected)

        event_buttons = ttk.Frame(event_frame)
        event_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(event_buttons, text="Add Event", command=self._add_event).pack(side="left")
        ttk.Button(event_buttons, text="Delete Selected", command=self._delete_event).pack(
            side="left", padx=(8, 0)
        )

        form = ttk.Frame(edit_frame)
        form.pack(fill="both", expand=True)
        self._form_row(form, 0, "Kind", ttk.Combobox(
            form,
            textvariable=self.kind_var,
            values=("note", "rest"),
            state="readonly",
            width=18,
        ))
        self._form_row(form, 1, "Beat", ttk.Entry(form, textvariable=self.beat_var, width=20))
        self._form_row(
            form,
            2,
            "Duration (beats)",
            ttk.Entry(form, textvariable=self.duration_var, width=20),
        )
        self._form_row(form, 3, "String index", ttk.Entry(form, textvariable=self.string_var, width=20))
        self._form_row(form, 4, "Fret", ttk.Entry(form, textvariable=self.fret_var, width=20))
        self._form_row(
            form,
            5,
            "Techniques",
            ttk.Entry(form, textvariable=self.techniques_var, width=28),
        )
        self._form_row(
            form,
            6,
            "Review note",
            ttk.Entry(form, textvariable=self.reviewer_note_var, width=28),
        )
        ttk.Label(
            form,
            text="Techniques: comma-separated. For rests, string/fret/techniques are cleared.",
            wraplength=330,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 6))
        ttk.Button(form, text="Save Correction", command=self._save_correction).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )
        form.columnconfigure(1, weight=1)

        warnings_frame = ttk.LabelFrame(self, text="Recognition / deterministic warnings", padding=8)
        warnings_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.warning_text = tk.Text(warnings_frame, height=5, wrap="word", state="disabled")
        self.warning_text.pack(fill="x")

        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill="x")
        ttk.Button(footer, text="Save Review", command=self._save).pack(side="left")
        ttk.Label(footer, text="Practice BPM:").pack(side="left", padx=(16, 4))
        ttk.Entry(footer, textvariable=self.bpm_var, width=8).pack(side="left")
        ttk.Button(
            footer,
            text="Export Reviewed Fixture",
            command=self._export_reviewed_fixture,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(footer, text="Close", command=self._close).pack(side="right")

    @staticmethod
    def _form_row(parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        widget.grid(row=row, column=1, sticky="ew", pady=3)

    def _current_measure(self) -> ReviewedScoreMeasure:
        return self.record.measures[self.measure_position]

    def _candidate_measure(self):
        index = self._current_measure().measure_index
        return next(measure for measure in self.candidates.measures if measure.measure_index == index)

    def _render_measure(self) -> None:
        measure = self._current_measure()
        total = len(self.record.measures)
        self.measure_counter_var.set(f"Measure {measure.measure_index + 1}  ({self.measure_position + 1}/{total})")
        self.measure_status_var.set(f"Status: {measure.status.upper()}")
        reviewed = sum(item.status != "pending" for item in self.record.measures)
        self.global_status_var.set(f"{reviewed}/{total} measures reviewed")

        x0, y0, x1, y1 = measure.region
        crop = self._page_image.crop((x0, y0, x1, y1))
        max_width, max_height = 1080, 270
        scale = min(max_width / max(crop.width, 1), max_height / max(crop.height, 1), 1.5)
        if scale != 1.0:
            crop = crop.resize(
                (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
                Image.Resampling.LANCZOS,
            )
        self._photo = ImageTk.PhotoImage(crop)
        self.image_label.configure(image=self._photo)

        self._render_events()
        self._render_warnings()
        self._clear_form()

    def _render_events(self) -> None:
        self.event_tree.delete(*self.event_tree.get_children())
        for index, event in enumerate(self._current_measure().events):
            self.event_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    index + 1,
                    event.kind,
                    f"{event.beat:g}",
                    f"{event.duration_beats:g}",
                    "" if event.string is None else event.string,
                    "" if event.fret is None else event.fret,
                    ", ".join(event.techniques),
                    event.action,
                ),
            )

    def _render_warnings(self) -> None:
        candidate = self._candidate_measure()
        lines = list(candidate.deterministic_warnings)
        if candidate.geometry_review_required:
            lines.insert(0, "geometry_review_required")
        if candidate.response.ambiguity_notes:
            lines.extend(f"model: {line}" for line in candidate.response.ambiguity_notes)
        if not lines:
            lines = ["No deterministic warnings for this measure. Visual human confirmation is still required."]
        self.warning_text.configure(state="normal")
        self.warning_text.delete("1.0", "end")
        self.warning_text.insert("end", "\n".join(lines))
        self.warning_text.configure(state="disabled")

    def _event_selected(self, _event=None) -> None:
        selection = self.event_tree.selection()
        if not selection:
            return
        event = self._current_measure().events[int(selection[0])]
        self.kind_var.set(event.kind)
        self.beat_var.set(f"{event.beat:g}")
        self.duration_var.set(f"{event.duration_beats:g}")
        self.string_var.set("" if event.string is None else str(event.string))
        self.fret_var.set("" if event.fret is None else str(event.fret))
        self.techniques_var.set(", ".join(event.techniques))
        self.reviewer_note_var.set(event.reviewer_note or "")

    def _clear_form(self) -> None:
        self.kind_var.set("note")
        self.beat_var.set("")
        self.duration_var.set("")
        self.string_var.set("")
        self.fret_var.set("")
        self.techniques_var.set("")
        self.reviewer_note_var.set("")

    def _event_from_form(self, *, source_event_index: int | None, action: str) -> ReviewedScoreEvent:
        kind = self.kind_var.get().strip()
        if kind not in {"note", "rest"}:
            raise ValueError("kind must be note or rest")
        beat = float(self.beat_var.get())
        duration = float(self.duration_var.get())
        techniques = [
            value.strip()
            for value in self.techniques_var.get().split(",")
            if value.strip()
        ]
        reviewer_note = self.reviewer_note_var.get().strip() or None

        original_confidence = None
        if source_event_index is not None:
            original = self._candidate_measure().response.events[source_event_index]
            original_confidence = original.confidence

        if kind == "rest":
            string = None
            fret = None
            techniques = []
        else:
            string = int(self.string_var.get())
            fret = int(self.fret_var.get())

        return ReviewedScoreEvent(
            source_event_index=source_event_index,
            action=action,
            kind=kind,
            beat=beat,
            duration_beats=duration,
            string=string,
            fret=fret,
            techniques=techniques,
            original_vision_confidence=original_confidence,
            reviewer_note=reviewer_note,
        )

    def _replace_measure(self, replacement: ReviewedScoreMeasure) -> None:
        measures = list(self.record.measures)
        measures[self.measure_position] = replacement
        self.record = self.record.model_copy(update={"measures": measures})

    def _save_correction(self) -> None:
        selection = self.event_tree.selection()
        if not selection:
            messagebox.showinfo("Printed Score Review", "Select an event to correct.", parent=self)
            return
        index = int(selection[0])
        measure = self._current_measure()
        old = measure.events[index]
        try:
            corrected = self._event_from_form(
                source_event_index=old.source_event_index,
                action="added" if old.source_event_index is None else "corrected",
            )
        except Exception as exc:
            messagebox.showerror("Printed Score Review", f"Invalid event values:\n{exc}", parent=self)
            return
        events = list(measure.events)
        events[index] = corrected
        replacement = measure.model_copy(update={"events": events, "status": "pending"})
        self._replace_measure(replacement)
        self._save(silent=True)
        self._render_measure()
        self.event_tree.selection_set(str(index))
        self._event_selected()

    def _add_event(self) -> None:
        if not self.beat_var.get().strip() or not self.duration_var.get().strip():
            self.beat_var.set("1")
            self.duration_var.set("1")
            if self.kind_var.get() == "note":
                self.string_var.set("0")
                self.fret_var.set("0")
            messagebox.showinfo(
                "Printed Score Review",
                "Enter the new event values, then click Add Event again.",
                parent=self,
            )
            return
        try:
            added = self._event_from_form(source_event_index=None, action="added")
        except Exception as exc:
            messagebox.showerror("Printed Score Review", f"Invalid event values:\n{exc}", parent=self)
            return
        measure = self._current_measure()
        replacement = measure.model_copy(
            update={"events": [*measure.events, added], "status": "pending"}
        )
        self._replace_measure(replacement)
        self._save(silent=True)
        self._render_measure()

    def _delete_event(self) -> None:
        selection = self.event_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        measure = self._current_measure()
        event = measure.events[index]
        events = list(measure.events)
        events.pop(index)
        discarded = list(measure.discarded_source_event_indexes)
        if event.source_event_index is not None and event.source_event_index not in discarded:
            discarded.append(event.source_event_index)
            discarded.sort()
        replacement = measure.model_copy(
            update={
                "events": events,
                "discarded_source_event_indexes": discarded,
                "status": "pending",
            }
        )
        self._replace_measure(replacement)
        self._save(silent=True)
        self._render_measure()

    def _approve_measure(self) -> None:
        measure = self._current_measure()
        changed = bool(measure.discarded_source_event_indexes) or any(
            event.action != "approved" for event in measure.events
        )
        status = "corrected" if changed else "approved"
        self._replace_measure(measure.model_copy(update={"status": status}))
        self._save(silent=True)
        self._render_measure()
        if self.measure_position < len(self.record.measures) - 1:
            self.measure_position += 1
            self._render_measure()

    def _mark_pending(self) -> None:
        measure = self._current_measure()
        self._replace_measure(measure.model_copy(update={"status": "pending"}))
        self._save(silent=True)
        self._render_measure()

    def _previous_measure(self) -> None:
        if self.measure_position > 0:
            self.measure_position -= 1
            self._render_measure()

    def _next_measure(self) -> None:
        if self.measure_position < len(self.record.measures) - 1:
            self.measure_position += 1
            self._render_measure()

    def _save(self, *, silent: bool = False) -> None:
        try:
            path = save_review_record(self.project_root, self.record)
        except Exception as exc:
            if not silent:
                messagebox.showerror("Printed Score Review", f"Could not save review:\n{exc}", parent=self)
            return
        if not silent:
            messagebox.showinfo("Printed Score Review", f"Review saved:\n{path}", parent=self)

    def _export_reviewed_fixture(self) -> None:
        try:
            bpm = float(self.bpm_var.get())
            path = write_reviewed_fixture(self.project_root, self.record, bpm=bpm)
        except Exception as exc:
            messagebox.showerror(
                "Printed Score Review",
                f"Reviewed fixture is not ready:\n{exc}",
                parent=self,
            )
            return
        self._save(silent=True)
        messagebox.showinfo(
            "Printed Score Review",
            f"Human-reviewed fixture written:\n{path}",
            parent=self,
        )

    def _close(self) -> None:
        self._save(silent=True)
        self.destroy()


def open_printed_score_review(
    master: tk.Misc,
    project_dir: Path,
    candidate_path: Path,
    *,
    default_bpm: float = 80.0,
) -> PrintedScoreReviewWindow:
    return PrintedScoreReviewWindow(
        master,
        project_dir,
        candidate_path,
        default_bpm=default_bpm,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cdlc-score-review",
        description="Review private printed-score recognition candidates measure by measure",
    )
    parser.add_argument("project", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--bpm", type=float, default=80.0)
    args = parser.parse_args(argv)

    root = tk.Tk()
    root.withdraw()
    try:
        window = PrintedScoreReviewWindow(root, args.project, args.candidates, default_bpm=args.bpm)
    except Exception as exc:
        root.destroy()
        raise SystemExit(f"Could not open printed-score review: {exc}") from exc
    window.focus_force()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
