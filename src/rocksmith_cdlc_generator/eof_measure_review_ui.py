from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .desktop_theme import PALETTE
from .eof_hand_position_project import load_current_project_eof_hand_position_status
from .eof_live_preview import highway_notes, live_window, notes_in_window, string_count, time_fraction
from .eof_measure_review import MeasureWindow, build_measure_windows, measure_index_for_time, summarize_measure_fingering


# EOF can use a Rocksmith-oriented lane color set. Keep the same core idea here while
# also rendering fret numbers and review outlines so color is never the only signal.
_STRING_COLORS = ("#F04444", "#F3C846", "#4E7BEF", "#F18B3A", "#5ECF67", "#B86CE3", "#57C8D9", "#E58DA8")
_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _midi_name(value: int) -> str:
    return f"{_NOTE_NAMES[value % 12]}{value // 12 - 1}"


class EOFMeasureReviewMixin:
    """EOF-inspired live arrangement review using the project-owned authoring clock.

    The view is intentionally visual and playback-synchronized: an upper 2D string-lane
    surface and a lower perspective fretboard/highway render the same current arrangement.
    EOF is a behavioral/reference implementation only; no EOF state becomes project authority.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._eof_measure_windows: list[MeasureWindow] = []
        self._eof_measure_index: int | None = None
        self._eof_tab_hits: list[tuple[float, float, float, float, float]] = []
        self._eof_highway_hits: list[tuple[float, float, float, float, float]] = []
        super().__init__(*args, **kwargs)

    def set_project(self, project) -> None:
        self._eof_measure_windows = []
        self._eof_measure_index = None
        self._eof_tab_hits = []
        self._eof_highway_hits = []
        super().set_project(project)

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()

        box = ttk.LabelFrame(
            self.arrangement_preview_tab,
            text="Live fingering preview · EOF / Rocksmith inspired",
            padding=8,
        )
        box.pack(fill="both", expand=True, pady=(8, 8), before=self.arrangement_canvas)

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Label(toolbar, text="Arrangement").pack(side="left")
        self.eof_live_role_combo = ttk.Combobox(
            toolbar,
            textvariable=self.fretboard_role_var,
            values=("lead", "rhythm", "bass"),
            state="readonly",
            width=9,
        )
        self.eof_live_role_combo.pack(side="left", padx=(6, 12))
        self.eof_live_role_combo.bind("<<ComboboxSelected>>", self._eof_live_role_changed)
        ttk.Button(toolbar, text="◀ Previous bar", command=lambda: self._step_measure(-1)).pack(side="left")
        ttk.Button(toolbar, text="Next bar ▶", command=lambda: self._step_measure(1)).pack(side="left", padx=(6, 0))

        self.eof_measure_follow_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            toolbar,
            text="Follow playback",
            variable=self.eof_measure_follow_var,
            command=self._refresh_eof_live_preview,
        ).pack(side="left", padx=(14, 0))

        self.eof_measure_status_var = tk.StringVar(value="Waiting for authoritative arrangement timing…")
        ttk.Label(toolbar, textvariable=self.eof_measure_status_var, justify="left").pack(
            side="left", fill="x", expand=True, padx=(14, 0)
        )

        self.eof_measure_fret_var = tk.StringVar(value="")
        ttk.Label(
            box,
            textvariable=self.eof_measure_fret_var,
            justify="left",
            wraplength=1250,
        ).pack(fill="x", pady=(0, 6))

        ttk.Label(
            box,
            text="2D string lanes · fret numbers, sustains, beats and bar lines move with the song",
            style="Muted.TLabel",
        ).pack(anchor="w")
        self.eof_tab_canvas = tk.Canvas(
            box,
            height=235,
            background=PALETTE.canvas,
            highlightthickness=1,
            highlightbackground=PALETTE.border_strong,
        )
        self.eof_tab_canvas.pack(fill="x", expand=False, pady=(3, 8))
        self.eof_tab_canvas.bind("<Configure>", lambda _event: self._draw_eof_tab())
        self.eof_tab_canvas.bind("<Button-1>", self._eof_tab_clicked)

        ttk.Label(
            box,
            text="Perspective fretboard · upcoming physical positions use the same playback clock",
            style="Muted.TLabel",
        ).pack(anchor="w")
        self.eof_highway_canvas = tk.Canvas(
            box,
            height=255,
            background=PALETTE.canvas,
            highlightthickness=1,
            highlightbackground=PALETTE.border_strong,
        )
        self.eof_highway_canvas.pack(fill="x", expand=False, pady=(3, 0))
        self.eof_highway_canvas.bind("<Configure>", lambda _event: self._draw_eof_highway())
        self.eof_highway_canvas.bind("<Button-1>", self._eof_highway_clicked)

        # The previous dense whole-song lane plot was useful diagnostically but is not a
        # good primary authoring surface. Keep its underlying model intact and hide only
        # that canvas; the existing review controls below remain available.
        self.arrangement_canvas.pack_forget()

        if hasattr(self, "fretboard_role_combo"):
            self.fretboard_role_combo.bind("<<ComboboxSelected>>", self._eof_live_role_changed, add="+")

    def refresh(self) -> None:
        super().refresh()
        preview = getattr(self, "score_preview", None)
        self._eof_measure_windows = build_measure_windows(preview) if preview is not None else []
        available = [arr.instrument for arr in preview.arrangements] if preview is not None else []
        if hasattr(self, "eof_live_role_combo"):
            self.eof_live_role_combo.configure(values=available)
        if not self._eof_measure_windows:
            self._eof_measure_index = None
        else:
            when = float(getattr(self, "_selected_time", None) or 0.0)
            self._eof_measure_index = measure_index_for_time(self._eof_measure_windows, when)
        self._refresh_eof_live_preview()

    def _poll_playback(self) -> None:
        # PlaybackSongWorkspaceWindow updates `_selected_time` from the real audio
        # transport every 50 ms. Repaint immediately afterward so both EOF-inspired
        # panes visibly travel with the song rather than acting as static inspectors.
        super()._poll_playback()
        if hasattr(self, "eof_tab_canvas"):
            self._refresh_eof_live_preview(redraw_only=True)

    def _seek_to(self, seconds: float) -> None:
        super()._seek_to(seconds)
        if hasattr(self, "eof_tab_canvas"):
            self._refresh_eof_live_preview(redraw_only=True)

    def _stop(self) -> None:
        super()._stop()
        if hasattr(self, "eof_tab_canvas"):
            self._refresh_eof_live_preview(redraw_only=True)

    def _eof_live_role_changed(self, _event=None) -> None:
        role = self.fretboard_role_var.get()
        if hasattr(self, "fretboard_role_var"):
            self.fretboard_role_var.set(role)
        self._draw_fretboard()
        self._refresh_eof_live_preview()

    def _step_measure(self, delta: int) -> None:
        if not self._eof_measure_windows:
            return
        if self._eof_measure_index is None:
            self._eof_measure_index = 0
        else:
            self._eof_measure_index = min(max(self._eof_measure_index + delta, 0), len(self._eof_measure_windows) - 1)
        measure = self._eof_measure_windows[self._eof_measure_index]
        self._seek_to(measure.start_seconds)
        self._refresh_eof_live_preview()

    def _active_measure_arrangement(self):
        preview = getattr(self, "score_preview", None)
        if preview is None:
            return None
        role = self.fretboard_role_var.get() if hasattr(self, "fretboard_role_var") else ""
        return next((item for item in preview.arrangements if item.instrument == role), None)

    def _refresh_eof_live_preview(self, *, redraw_only: bool = False) -> None:
        if not hasattr(self, "eof_measure_status_var"):
            return
        preview = getattr(self, "score_preview", None)
        arrangement = self._active_measure_arrangement()
        if preview is None or arrangement is None:
            self.eof_measure_status_var.set("Live preview unavailable until an arrangement draft exists.")
            self.eof_measure_fret_var.set("")
            self._draw_eof_tab()
            self._draw_eof_highway()
            return

        when = float(getattr(self, "_selected_time", None) or 0.0)
        index = measure_index_for_time(self._eof_measure_windows, when)
        if self.eof_measure_follow_var.get() and index is not None:
            self._eof_measure_index = index
        if self._eof_measure_index is None and self._eof_measure_windows:
            self._eof_measure_index = 0

        if self._eof_measure_index is not None and self._eof_measure_windows:
            measure = self._eof_measure_windows[self._eof_measure_index]
            self.eof_measure_status_var.set(
                f"{arrangement.instrument.title()} · bar {measure.number}/{len(self._eof_measure_windows)} · "
                f"{measure.numerator}/{measure.denominator} · playhead {when:.3f}s"
            )
            if not redraw_only:
                summary = summarize_measure_fingering(arrangement, measure)
                evidence_text = ""
                try:
                    eof_status = load_current_project_eof_hand_position_status(self.project)
                except Exception:
                    eof_status = None
                if eof_status is not None and eof_status.instrument == arrangement.instrument:
                    evidence_text = f" · EOF FHP evidence {eof_status.evidence.observation_count} markers"
                self.eof_measure_fret_var.set(
                    f"Bar fingering: {summary.event_count} events · {summary.fret_span_text} · "
                    f"open {summary.open_string_count} · unresolved {summary.unresolved_position_count} · "
                    f"review-required {summary.review_required_count}{evidence_text}"
                )
        else:
            self.eof_measure_status_var.set(f"{arrangement.instrument.title()} · playhead {when:.3f}s")
            if not redraw_only:
                self.eof_measure_fret_var.set("Bar metadata unavailable; live note positions still use the project clock.")

        self._draw_eof_tab()
        self._draw_eof_highway()

    def _preview_duration(self) -> float:
        snapshot = getattr(self, "snapshot", None)
        if snapshot is not None:
            return float(snapshot.duration_seconds)
        preview = getattr(self, "score_preview", None)
        if preview is None:
            return 0.0
        values = [note.end_seconds for arrangement in preview.arrangements for note in arrangement.notes]
        return max(values, default=0.0)

    def _live_window(self):
        return live_window(
            playhead_seconds=float(getattr(self, "_selected_time", None) or 0.0),
            duration_seconds=self._preview_duration(),
        )

    def _draw_eof_tab(self) -> None:
        if not hasattr(self, "eof_tab_canvas"):
            return
        canvas = self.eof_tab_canvas
        canvas.delete("all")
        self._eof_tab_hits = []
        arrangement = self._active_measure_arrangement()
        if arrangement is None:
            canvas.create_text(20, 30, text="No arrangement available", anchor="w", fill=PALETTE.text_muted)
            return

        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 210)
        margin_left, margin_right = 58.0, 24.0
        top, bottom = 28.0, height - 28.0
        strings = max(string_count(arrangement), 1)
        window = self._live_window()
        usable_w = max(width - margin_left - margin_right, 1.0)
        usable_h = max(bottom - top, 1.0)

        # Beat and measure grid first, matching EOF's editor emphasis on musical time.
        preview = getattr(self, "score_preview", None)
        if preview is not None:
            for beat_index, beat in enumerate(preview.beat_times_seconds):
                if not (window.start_seconds <= beat <= window.end_seconds):
                    continue
                x = margin_left + time_fraction(beat, window) * usable_w
                canvas.create_line(x, top - 12, x, bottom + 10, fill=PALETTE.border, dash=(2, 4))
            for measure in self._eof_measure_windows:
                if window.start_seconds <= measure.start_seconds <= window.end_seconds:
                    x = margin_left + time_fraction(measure.start_seconds, window) * usable_w
                    canvas.create_line(x, top - 18, x, bottom + 12, fill=PALETTE.text_muted, width=2)
                    canvas.create_text(x + 4, 5, text=str(measure.number), anchor="nw", fill=PALETTE.text_muted)

        tuning = arrangement.tuning_midi or []
        for string_index in range(strings):
            y = top + (string_index + 0.5) * usable_h / strings
            label = _midi_name(tuning[string_index]) if string_index < len(tuning) else f"S{string_index + 1}"
            canvas.create_text(8, y, text=label, anchor="w", fill=_STRING_COLORS[string_index % len(_STRING_COLORS)], font=("Segoe UI", 10, "bold"))
            canvas.create_line(margin_left, y, width - margin_right, y, fill=PALETTE.info, width=1)

        for note in notes_in_window(arrangement, window):
            if note.string_index is None or note.string_index >= strings:
                continue
            y = top + (note.string_index + 0.5) * usable_h / strings
            x1 = margin_left + time_fraction(note.start_seconds, window) * usable_w
            x2 = margin_left + time_fraction(note.end_seconds, window) * usable_w
            x2 = max(x2, x1 + 8)
            color = _STRING_COLORS[note.string_index % len(_STRING_COLORS)]
            canvas.create_line(x1, y, x2, y, fill=color, width=8)
            outline = PALETTE.warning if note.review_required else PALETTE.text
            canvas.create_rectangle(x1 - 8, y - 11, x1 + 8, y + 11, fill=PALETTE.surface, outline=outline, width=2 if note.review_required else 1)
            canvas.create_text(x1, y, text="?" if note.fret is None else str(note.fret), fill=color, font=("Segoe UI", 9, "bold"))
            if note.techniques:
                canvas.create_text(x1 + 10, y - 13, text="/".join(note.techniques[:2]), anchor="sw", fill=PALETTE.text_muted, font=("Segoe UI", 8))
            self._eof_tab_hits.append((x1 - 10, y - 13, x1 + 10, y + 13, note.start_seconds))

        playhead_x = margin_left + time_fraction(window.playhead_seconds, window) * usable_w
        canvas.create_line(playhead_x, top - 20, playhead_x, bottom + 14, fill=PALETTE.accent_hover, width=3)
        canvas.create_text(playhead_x + 5, height - 5, text=f"{window.playhead_seconds:.2f}s", anchor="sw", fill=PALETTE.accent_hover)

    def _draw_eof_highway(self) -> None:
        if not hasattr(self, "eof_highway_canvas"):
            return
        canvas = self.eof_highway_canvas
        canvas.delete("all")
        self._eof_highway_hits = []
        arrangement = self._active_measure_arrangement()
        if arrangement is None:
            return

        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 230)
        strings = max(string_count(arrangement), 1)
        window = self._live_window()
        center_x = width / 2
        horizon_y = 28.0
        near_y = height - 28.0
        horizon_half = width * 0.16
        near_half = width * 0.43

        canvas.create_text(12, 9, text="NOW", anchor="nw", fill=PALETTE.accent_hover, font=("Segoe UI", 9, "bold"))
        canvas.create_line(center_x - near_half, near_y, center_x + near_half, near_y, fill=PALETTE.accent_hover, width=3)

        def edges(progress: float) -> tuple[float, float, float]:
            y = near_y - progress * (near_y - horizon_y)
            half = near_half - progress * (near_half - horizon_half)
            return center_x - half, center_x + half, y

        # Perspective time grid.
        for fraction in (0.25, 0.5, 0.75, 1.0):
            left, right, y = edges(fraction)
            canvas.create_line(left, y, right, y, fill=PALETTE.border)
            seconds = window.playhead_seconds + fraction * max(window.end_seconds - window.playhead_seconds, 0.0)
            canvas.create_text(right + 5, y, text=f"{seconds:.1f}", anchor="w", fill=PALETTE.text_muted, font=("Segoe UI", 8))

        # String rails converge toward the horizon exactly like a note highway.
        for string_index in range(strings):
            fraction = (string_index + 0.5) / strings
            near_x = (center_x - near_half) + fraction * (near_half * 2)
            far_x = (center_x - horizon_half) + fraction * (horizon_half * 2)
            color = _STRING_COLORS[string_index % len(_STRING_COLORS)]
            canvas.create_line(near_x, near_y, far_x, horizon_y, fill=PALETTE.info, width=1)
            canvas.create_text(near_x, near_y + 5, text=str(string_index + 1), anchor="n", fill=color, font=("Segoe UI", 9, "bold"))

        for projected in sorted(highway_notes(arrangement, window), key=lambda item: item.progress, reverse=True):
            note = projected.note
            if note.string_index is None or note.string_index >= strings:
                continue
            left, right, y = edges(projected.progress)
            x = left + projected.x_fraction * (right - left)
            scale = 1.0 - projected.progress * 0.55
            half_w = max(7.0 * scale, 3.0)
            half_h = max(10.0 * scale, 4.0)
            color = _STRING_COLORS[note.string_index % len(_STRING_COLORS)]
            outline = PALETTE.warning if note.review_required else PALETTE.text
            canvas.create_polygon(
                x - half_w, y + half_h,
                x + half_w, y + half_h,
                x + half_w * 0.72, y - half_h,
                x - half_w * 0.72, y - half_h,
                fill=color,
                outline=outline,
                width=2 if note.review_required else 1,
            )
            canvas.create_text(x, y, text="?" if note.fret is None else str(note.fret), fill=PALETTE.canvas, font=("Segoe UI", max(int(9 * scale), 6), "bold"))
            self._eof_highway_hits.append((x - half_w - 4, y - half_h - 4, x + half_w + 4, y + half_h + 4, note.start_seconds))

        # Chord context: simultaneous notes at the next onset are visually named as a
        # physical shape even when canonical chord naming is unavailable.
        upcoming = [n for n in arrangement.notes if n.start_seconds >= window.playhead_seconds - 0.02 and n.start_seconds <= window.end_seconds]
        if upcoming:
            first = min(n.start_seconds for n in upcoming)
            chord = [n for n in upcoming if abs(n.start_seconds - first) <= 0.025]
            if len(chord) > 1:
                shape = "  ".join(
                    f"S{n.string_index + 1 if n.string_index is not None else '?'}:{n.fret if n.fret is not None else '?'}"
                    for n in sorted(chord, key=lambda item: item.string_index if item.string_index is not None else 99)
                )
                canvas.create_text(center_x, 7, text=f"Next chord · {shape}", anchor="n", fill=PALETTE.text, font=("Segoe UI", 10, "bold"))

    def _eof_tab_clicked(self, event: tk.Event) -> None:
        for x1, y1, x2, y2, when in reversed(self._eof_tab_hits):
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._seek_to(when)
                return
        width = max(self.eof_tab_canvas.winfo_width(), 500)
        margin_left, margin_right = 58.0, 24.0
        fraction = min(max((event.x - margin_left) / max(width - margin_left - margin_right, 1.0), 0.0), 1.0)
        window = self._live_window()
        self._seek_to(window.start_seconds + fraction * window.span_seconds)

    def _eof_highway_clicked(self, event: tk.Event) -> None:
        for x1, y1, x2, y2, when in reversed(self._eof_highway_hits):
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._seek_to(when)
                return
