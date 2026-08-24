from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .desktop_theme import PALETTE
from .reviewed_positions import load_current_reviewed_positions, set_reviewed_position
from .score_preview import load_score_fanout_preview_snapshot
from .song_preview import PreviewReviewItem, PreviewReviewQueue, SongPreviewSnapshot, build_preview_review_queue
from .timing_review_ui import TimingReviewSongWorkspaceWindow


class ArrangementPreviewSongWorkspaceWindow(TimingReviewSongWorkspaceWindow):
    """Bass/Lead/Rhythm inspection with explicit provenance-aware position review."""

    def __init__(self, parent: tk.Misc, project: Path, *, run_callback=None) -> None:
        self.score_preview: SongPreviewSnapshot | None = None
        self.preview_review_queue = PreviewReviewQueue()
        self._preview_review_index: int | None = None
        super().__init__(parent, project, run_callback=run_callback)

    def set_project(self, project: Path) -> None:
        self.score_preview = None
        self.preview_review_queue = PreviewReviewQueue()
        self._preview_review_index = None
        super().set_project(project)

    def _build_layout(self) -> None:
        super()._build_layout()
        self.arrangement_preview_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.arrangement_preview_tab, text="Arrangement Preview")
        self._build_arrangement_preview()

    def _build_arrangement_preview(self) -> None:
        controls = ttk.Frame(self.arrangement_preview_tab)
        controls.pack(fill="x", pady=(0, 8))
        self.preview_status_var = tk.StringVar(value="Waiting for authoritative score fan-out…")
        ttk.Label(controls, textvariable=self.preview_status_var).pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text="◀ Previous review", command=lambda: self._move_review(-1)).pack(side="right")
        ttk.Button(controls, text="Next review ▶", command=lambda: self._move_review(1)).pack(side="right", padx=(6, 0))
        ttk.Button(controls, text="Zoom −", command=lambda: self._change_zoom(0.5)).pack(side="right", padx=(6, 0))
        ttk.Button(controls, text="Zoom +", command=lambda: self._change_zoom(2.0)).pack(side="right", padx=(6, 0))

        self.arrangement_canvas = tk.Canvas(
            self.arrangement_preview_tab,
            height=300,
            highlightthickness=1,
            background=PALETTE.canvas,
            highlightbackground=PALETTE.border_strong,
        )
        self.arrangement_canvas.pack(fill="both", expand=True)
        self.arrangement_canvas.bind("<Configure>", lambda _event: self._draw_arrangement_preview())
        self.arrangement_canvas.bind("<Button-1>", self._arrangement_clicked)

        lower = ttk.Panedwindow(self.arrangement_preview_tab, orient="horizontal")
        lower.pack(fill="x", pady=(8, 0))
        fret_box = ttk.LabelFrame(lower, text="Synchronized fretboard", padding=8)
        detail_box = ttk.LabelFrame(lower, text="Current review item", padding=8)
        lower.add(fret_box, weight=3)
        lower.add(detail_box, weight=2)

        header = ttk.Frame(fret_box)
        header.pack(fill="x", pady=(0, 4))
        ttk.Label(header, text="Arrangement").pack(side="left")
        self.fretboard_role_var = tk.StringVar(value="lead")
        self.fretboard_role_combo = ttk.Combobox(
            header,
            textvariable=self.fretboard_role_var,
            values=("lead", "rhythm", "bass"),
            state="readonly",
            width=9,
        )
        self.fretboard_role_combo.pack(side="left", padx=(5, 0))
        self.fretboard_role_combo.bind("<<ComboboxSelected>>", lambda _event: self._draw_fretboard())
        self.fretboard_canvas = tk.Canvas(
            fret_box,
            height=190,
            highlightthickness=1,
            background=PALETTE.canvas,
            highlightbackground=PALETTE.border,
        )
        self.fretboard_canvas.pack(fill="x", expand=True)
        self.fretboard_canvas.bind("<Configure>", lambda _event: self._draw_fretboard())

        self.preview_detail_var = tk.StringVar(
            value="Review-required events from all arrangements are ordered chronologically."
        )
        ttk.Label(detail_box, textvariable=self.preview_detail_var, wraplength=430, justify="left").pack(anchor="w")

        position_box = ttk.LabelFrame(detail_box, text="Human-reviewed physical position", padding=7)
        position_box.pack(fill="x", pady=(10, 0))
        row = ttk.Frame(position_box)
        row.pack(fill="x")
        ttk.Label(row, text="String (1-based)").pack(side="left")
        self.position_string_var = tk.StringVar(value="")
        ttk.Spinbox(row, from_=1, to=8, width=5, textvariable=self.position_string_var).pack(side="left", padx=(5, 12))
        ttk.Label(row, text="Fret").pack(side="left")
        self.position_fret_var = tk.StringVar(value="")
        ttk.Spinbox(row, from_=0, to=36, width=5, textvariable=self.position_fret_var).pack(side="left", padx=(5, 0))
        self.accept_position_button = ttk.Button(
            position_box,
            text="Accept Position",
            command=self._accept_reviewed_position,
            state="disabled",
        )
        self.accept_position_button.pack(anchor="e", pady=(7, 0))
        self.position_status_var = tk.StringVar(
            value="Choose a review item. Acceptance is pitch-checked against the source tuning."
        )
        ttk.Label(position_box, textvariable=self.position_status_var, wraplength=410, justify="left").pack(anchor="w", pady=(7, 0))

        ttk.Label(
            detail_box,
            text=(
                "Accept Position records only string/fret placement. It does not confirm mapping, rights, "
                "timing, note pitch, techniques, overall note trust, validation, or package readiness."
            ),
            wraplength=430,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def refresh(self) -> None:
        super().refresh()
        if getattr(self, "_refresh_failed", False):
            return
        try:
            self.score_preview = load_score_fanout_preview_snapshot(self.project)
            self.preview_review_queue = build_preview_review_queue(self.score_preview)
        except Exception as exc:
            self.score_preview = None
            self.preview_review_queue = PreviewReviewQueue()
            self._preview_review_index = None
            if hasattr(self, "preview_status_var"):
                self.preview_status_var.set(f"Arrangement preview unavailable: {exc}")
        else:
            roles = ", ".join(arr.instrument.title() for arr in self.score_preview.arrangements)
            self.preview_status_var.set(
                f"{roles} · {sum(arr.note_count for arr in self.score_preview.arrangements)} events · "
                f"{len(self.preview_review_queue.items)} require review"
            )
            available = [arr.instrument for arr in self.score_preview.arrangements]
            self.fretboard_role_combo.configure(values=available)
            if self.fretboard_role_var.get() not in available and available:
                self.fretboard_role_var.set(available[0])
        self._draw_arrangement_preview()
        self._draw_fretboard()

    def _arrangement_clicked(self, event: tk.Event) -> None:
        if self.score_preview is None or self.snapshot is None:
            return
        width = max(self.arrangement_canvas.winfo_width(), 240)
        margin = 70.0
        usable = max(width - 2 * margin, 1.0)
        start, end = self._view_bounds()
        fraction = min(max((float(event.x) - margin) / usable, 0.0), 1.0)
        self._seek_to(start + fraction * (end - start))

    def _timeline_clicked(self, event: tk.Event) -> None:
        super()._timeline_clicked(event)
        self._draw_arrangement_preview()
        self._draw_fretboard()

    def _seek_to(self, seconds: float) -> None:
        super()._seek_to(seconds)
        if hasattr(self, "arrangement_canvas"):
            self._draw_arrangement_preview()
            self._draw_fretboard()

    def _stop(self) -> None:
        super()._stop()
        if hasattr(self, "arrangement_canvas"):
            self._draw_arrangement_preview()
            self._draw_fretboard()

    def _change_zoom(self, factor: float, *, focus_time: float | None = None) -> None:
        super()._change_zoom(factor, focus_time=focus_time)
        if hasattr(self, "arrangement_canvas"):
            self._draw_arrangement_preview()

    def _pan(self, fraction: float) -> None:
        super()._pan(fraction)
        if hasattr(self, "arrangement_canvas"):
            self._draw_arrangement_preview()

    def _preview_x(self, when: float, width: float) -> float:
        start, end = self._view_bounds()
        span = max(end - start, 0.001)
        margin = 70.0
        return margin + ((when - start) / span) * max(width - 2 * margin, 1.0)

    def _draw_arrangement_preview(self) -> None:
        if not hasattr(self, "arrangement_canvas"):
            return
        canvas = self.arrangement_canvas
        canvas.delete("all")
        preview = self.score_preview
        if preview is None or self.snapshot is None:
            canvas.create_text(
                20,
                30,
                text="Run score fan-out and promote shared timing to inspect synchronized arrangement events here.",
                anchor="w",
                fill=PALETTE.text_muted,
            )
            return
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 220)
        start, end = self._view_bounds()
        lanes = preview.arrangements
        lane_height = max((height - 35) / max(len(lanes), 1), 45)
        current_review = self._current_review_item()

        for lane_index, arrangement in enumerate(lanes):
            y0 = 20 + lane_index * lane_height
            y1 = y0 + lane_height - 8
            center = (y0 + y1) / 2
            lane_fill = PALETTE.surface if lane_index % 2 == 0 else PALETTE.surface_alt
            canvas.create_rectangle(70, y0, width - 70, y1, fill=lane_fill, outline=PALETTE.border)
            canvas.create_text(
                8,
                center,
                text=arrangement.instrument.title(),
                anchor="w",
                fill=PALETTE.text,
                font=("Segoe UI", 10, "bold"),
            )
            canvas.create_line(70, center, width - 70, center, fill=PALETTE.border_strong)
            for event_index, note in enumerate(arrangement.notes):
                if note.end_seconds < start or note.start_seconds > end:
                    continue
                x1 = self._preview_x(max(note.start_seconds, start), width)
                x2 = self._preview_x(min(note.end_seconds, end), width)
                if x2 - x1 < 3:
                    x2 = x1 + 3
                selected_review = bool(
                    current_review is not None
                    and current_review.instrument == arrangement.instrument
                    and current_review.event_index == event_index
                )
                if selected_review:
                    fill = PALETTE.accent
                    outline = PALETTE.text
                    outline_width = 3
                elif note.review_required:
                    fill = PALETTE.warning
                    outline = PALETTE.warning
                    outline_width = 2
                else:
                    fill = PALETTE.border_strong
                    outline = PALETTE.info
                    outline_width = 1
                canvas.create_rectangle(
                    x1,
                    y0 + 9,
                    x2,
                    y1 - 9,
                    width=outline_width,
                    fill=fill,
                    outline=outline,
                )
                if note.string_index is not None and note.fret is not None and x2 - x1 > 28:
                    text_fill = PALETTE.canvas if note.review_required and not selected_review else PALETTE.text
                    canvas.create_text(
                        (x1 + x2) / 2,
                        center,
                        text=f"s{note.string_index + 1}/f{note.fret}",
                        fill=text_fill,
                    )

        if self._selected_time is not None:
            x = self._preview_x(self._selected_time, width)
            canvas.create_line(x, 5, x, height - 5, width=3, fill=PALETTE.accent_hover)
            canvas.create_text(
                min(max(x + 5, 75), width - 75),
                8,
                text=f"{self._selected_time:.2f}s",
                anchor="nw",
                fill=PALETTE.accent_hover,
            )

    def _current_review_item(self) -> PreviewReviewItem | None:
        items = self.preview_review_queue.items
        index = self._preview_review_index
        if index is None or index < 0 or index >= len(items):
            return None
        return items[index]

    def _move_review(self, delta: int) -> None:
        items = self.preview_review_queue.items
        if not items:
            self.preview_detail_var.set("No score-fan-out events currently require review.")
            self.accept_position_button.configure(state="disabled")
            return
        if self._preview_review_index is None:
            index = 0 if delta >= 0 else len(items) - 1
        else:
            index = (self._preview_review_index + delta) % len(items)
        self._preview_review_index = index
        item = items[index]
        self._seek_to(item.start_seconds)
        self.fretboard_role_var.set(item.instrument)
        physical = (
            f"string {item.string_index + 1}, fret {item.fret}"
            if item.string_index is not None and item.fret is not None
            else "physical position unresolved"
        )
        techniques = ", ".join(item.techniques) if item.techniques else "none"
        self.preview_detail_var.set(
            f"{index + 1}/{len(items)} · {item.instrument.title()} event {item.event_index} · "
            f"{item.start_seconds:.3f}s recording time · {item.note_name or item.midi} · {physical}\n"
            f"confidence {item.import_confidence:.2f} · trust {item.trust_class.value} · techniques: {techniques}"
        )
        self.position_string_var.set(str(item.string_index + 1) if item.string_index is not None else "")
        self.position_fret_var.set(str(item.fret) if item.fret is not None else "")
        self.accept_position_button.configure(state="normal")
        try:
            layer = load_current_reviewed_positions(self.project)
            reviewed = (
                layer is not None
                and layer.decision_for(item.instrument, self._part_index(item.instrument), item.event_index) is not None
            )
        except Exception:
            reviewed = False
        self.position_status_var.set(
            "This event already has a current human-reviewed position; accepting again replaces that decision."
            if reviewed
            else "Position has not yet been explicitly accepted for this event."
        )
        self._draw_arrangement_preview()
        self._draw_fretboard()

    def _part_index(self, instrument: str) -> int:
        if self.score_preview is None:
            raise ValueError("Arrangement preview is unavailable")
        arrangement = next(
            (item for item in self.score_preview.arrangements if item.instrument == instrument),
            None,
        )
        if arrangement is None:
            raise ValueError(f"{instrument} arrangement is unavailable")
        return arrangement.part_index

    def _accept_reviewed_position(self) -> None:
        item = self._current_review_item()
        if item is None:
            return
        try:
            string_number = int(self.position_string_var.get())
            fret = int(self.position_fret_var.get())
            if string_number < 1:
                raise ValueError("String must be 1 or greater")
            set_reviewed_position(
                self.project,
                arrangement=item.instrument,
                event_index=item.event_index,
                string_index=string_number - 1,
                fret=fret,
            )
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror("Position Review", str(exc), parent=self)
            return

        self.position_status_var.set(
            "Position accepted. Imported score data was not changed; current guitar drafts are now stale until regenerated."
        )
        self.refresh()
        self._seek_to(item.start_seconds)

    def _draw_fretboard(self) -> None:
        if not hasattr(self, "fretboard_canvas"):
            return
        canvas = self.fretboard_canvas
        canvas.delete("all")
        preview = self.score_preview
        if preview is None:
            return
        role = self.fretboard_role_var.get()
        arrangement = next((item for item in preview.arrangements if item.instrument == role), None)
        if arrangement is None:
            return
        tuning = arrangement.tuning_midi or ([40, 45, 50, 55] if role == "bass" else [40, 45, 50, 55, 59, 64])
        strings = len(tuning)
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 150)
        left = 42
        right = width - 12
        top = 18
        bottom = height - 22
        max_fret = 24

        for fret in range(max_fret + 1):
            x = left + (right - left) * fret / max_fret
            canvas.create_line(
                x,
                top,
                x,
                bottom,
                width=2 if fret == 0 else 1,
                fill=PALETTE.border_strong if fret else PALETTE.info,
            )
            if fret in {0, 3, 5, 7, 9, 12, 15, 17, 19, 21, 24}:
                canvas.create_text(x, bottom + 10, text=str(fret), anchor="n", fill=PALETTE.text_muted)
        for string_index in range(strings):
            y = top + (bottom - top) * string_index / max(strings - 1, 1)
            canvas.create_line(left, y, right, y, fill=PALETTE.info)
            canvas.create_text(4, y, text=f"S{string_index + 1}", anchor="w", fill=PALETTE.text)

        when = float(self._selected_time or 0.0)
        active = [
            note for note in arrangement.notes
            if note.start_seconds <= when <= note.end_seconds and note.string_index is not None and note.fret is not None
        ]
        if not active:
            upcoming = [
                note for note in arrangement.notes
                if when <= note.start_seconds <= when + 0.20 and note.string_index is not None and note.fret is not None
            ]
            active = upcoming[:4]
        for note in active:
            if note.string_index is None or note.fret is None or note.string_index >= strings or note.fret > max_fret:
                continue
            x = left + (right - left) * note.fret / max_fret
            y = top + (bottom - top) * note.string_index / max(strings - 1, 1)
            fill = PALETTE.warning if note.review_required else PALETTE.accent
            canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill=fill, outline=PALETTE.text, width=2)
            canvas.create_text(x, y, text=str(note.fret), fill=PALETTE.canvas, font=("Segoe UI", 8, "bold"))

    def _poll_playback(self) -> None:
        playing = self.transport is not None and self.transport.playing
        super()._poll_playback()
        if playing and self.winfo_exists():
            self._draw_arrangement_preview()
            self._draw_fretboard()
