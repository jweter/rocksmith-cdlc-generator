from __future__ import annotations

from math import hypot
from time import perf_counter
import tkinter as tk
from tkinter import ttk

from .desktop_theme import PALETTE
from .eof_live_preview import highway_notes, string_count, time_fraction
from .human_review_marks import clear_event_mark, load_current_human_review_layer, mark_event


class LiveReviewEnhancementMixin:
    """Product Reality upgrades for the EOF/Rocksmith live preview.

    Keeps the existing audio transport and project clock authoritative while adding
    local transport controls, low-latency rendering behavior, selectable notes, and
    persistent human review marks.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._live_selected_event: tuple[str, int] | None = None
        self._live_last_render_ms = 0.0
        self._live_last_clock_delta_ms = 0.0
        super().__init__(*args, **kwargs)

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        live_box = None
        for child in self.arrangement_preview_tab.winfo_children():
            try:
                if isinstance(child, ttk.LabelFrame) and str(child.cget("text")).startswith("Live fingering preview"):
                    live_box = child
                    break
            except tk.TclError:
                continue
        if live_box is None:
            return

        transport = ttk.Frame(live_box)
        transport.pack(fill="x", pady=(0, 6), before=self.eof_tab_canvas)
        self.live_play_button = ttk.Button(transport, text="▶ Play", command=self._play_pause)
        self.live_play_button.pack(side="left")
        ttk.Button(transport, text="■ Stop", command=self._stop).pack(side="left", padx=(6, 0))
        ttk.Button(transport, text="◀ 5s", command=lambda: self._seek_relative(-5.0)).pack(side="left", padx=(10, 0))
        ttk.Button(transport, text="5s ▶", command=lambda: self._seek_relative(5.0)).pack(side="left", padx=(6, 0))
        ttk.Button(transport, text="First note", command=self._jump_first_note).pack(side="left", padx=(12, 0))
        ttk.Button(transport, text="Next note", command=self._jump_next_note).pack(side="left", padx=(6, 0))
        self.live_transport_time_var = tk.StringVar(value="0:00.00")
        ttk.Label(transport, textvariable=self.live_transport_time_var, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(12, 0))
        self.live_latency_var = tk.StringVar(value="render — · clock Δ —")
        ttk.Label(transport, textvariable=self.live_latency_var, style="Muted.TLabel").pack(side="right")

        review = ttk.LabelFrame(live_box, text="Selected note / chord review", padding=6)
        review.pack(fill="x", pady=(0, 6), before=self.eof_tab_canvas)
        self.live_selected_var = tk.StringVar(value="Click a fret number or note block to select it. Empty space still seeks.")
        ttk.Label(review, textvariable=self.live_selected_var, wraplength=850).pack(side="left", fill="x", expand=True)
        ttk.Button(review, text="Mark questionable", command=lambda: self._mark_selected("questionable")).pack(side="right", padx=(6, 0))
        ttk.Button(review, text="Mark wrong", command=lambda: self._mark_selected("wrong")).pack(side="right", padx=(6, 0))
        ttk.Button(review, text="Clear mark", command=self._clear_selected_mark).pack(side="right", padx=(6, 0))

    def _draw_timeline(self) -> None:
        """Do not repaint the expensive waveform while another tab is visible (#380)."""
        try:
            visible = self.notebook.select() == str(self.timeline_tab)
        except Exception:
            visible = True
        if visible:
            super()._draw_timeline()

    def _refresh_eof_live_preview(self, *, redraw_only: bool = False) -> None:
        started = perf_counter()
        displayed = float(getattr(self, "_selected_time", None) or 0.0)
        super()._refresh_eof_live_preview(redraw_only=redraw_only)
        self._live_last_render_ms = (perf_counter() - started) * 1000.0
        transport = getattr(self, "transport", None)
        if transport is not None:
            try:
                self._live_last_clock_delta_ms = abs(float(transport.position_seconds) - displayed) * 1000.0
            except Exception:
                self._live_last_clock_delta_ms = 0.0
        if hasattr(self, "live_latency_var"):
            self.live_latency_var.set(
                f"render {self._live_last_render_ms:.0f} ms · clock Δ {self._live_last_clock_delta_ms:.0f} ms"
            )
        if hasattr(self, "live_transport_time_var"):
            self.live_transport_time_var.set(self._format_time(displayed))
        if hasattr(self, "live_play_button"):
            playing = bool(transport is not None and transport.playing)
            self.live_play_button.configure(text="❚❚ Pause" if playing else "▶ Play")
        self._update_live_selected_summary()

    def _jump_first_note(self) -> None:
        arrangement = self._active_measure_arrangement()
        if arrangement is not None and arrangement.notes:
            self._seek_to(arrangement.notes[0].start_seconds)

    def _jump_next_note(self) -> None:
        arrangement = self._active_measure_arrangement()
        if arrangement is None:
            return
        now = float(getattr(self, "_selected_time", None) or 0.0)
        next_note = next((n for n in arrangement.notes if n.start_seconds > now + 0.015), None)
        if next_note is not None:
            self._seek_to(next_note.start_seconds)

    def _select_note(self, note) -> None:
        arrangement = self._active_measure_arrangement()
        if arrangement is None:
            return
        self._live_selected_event = (arrangement.instrument, note.event_index)
        self._seek_to(note.start_seconds)
        self._update_live_selected_summary()
        self._draw_eof_tab()
        self._draw_eof_highway()

    def _selected_note(self):
        arrangement = self._active_measure_arrangement()
        if arrangement is None or self._live_selected_event is None:
            return None
        role, event_index = self._live_selected_event
        if role != arrangement.instrument:
            return None
        return next((n for n in arrangement.notes if n.event_index == event_index), None)

    def _update_live_selected_summary(self) -> None:
        if not hasattr(self, "live_selected_var"):
            return
        note = self._selected_note()
        arrangement = self._active_measure_arrangement()
        if note is None or arrangement is None:
            self.live_selected_var.set("Click a fret number or note block to select it. Empty space still seeks.")
            return
        source_sha = getattr(getattr(self, "score_preview", None), "source_sha256", "")
        layer = load_current_human_review_layer(self.project, source_sha) if source_sha else None
        mark = None if layer is None else next((m for m in layer.marks if m.arrangement == arrangement.instrument and m.event_index == note.event_index), None)
        mark_text = f" · HUMAN {mark.state.upper()}" if mark is not None else ""
        techniques = ", ".join(note.techniques) if note.techniques else "none"
        self.live_selected_var.set(
            f"{arrangement.instrument.title()} event {note.event_index} · {note.start_seconds:.3f}s · MIDI {note.midi} · "
            f"string {note.string_index + 1 if note.string_index is not None else '?'} · fret {note.fret if note.fret is not None else '?'} · "
            f"techniques {techniques} · trust {note.trust_class.value} · confidence {note.import_confidence:.2f}{mark_text}"
        )

    def _mark_selected(self, state: str) -> None:
        note = self._selected_note()
        arrangement = self._active_measure_arrangement()
        preview = getattr(self, "score_preview", None)
        if note is None or arrangement is None or preview is None:
            return
        mark_event(
            self.project,
            source_sha256=preview.source_sha256,
            arrangement=arrangement.instrument,
            event_index=note.event_index,
            source_start_seconds=note.start_seconds,
            midi=note.midi,
            string_index=note.string_index,
            fret=note.fret,
            state=state,
        )
        self._update_live_selected_summary()
        self._draw_eof_tab()
        self._draw_eof_highway()

    def _clear_selected_mark(self) -> None:
        note = self._selected_note()
        arrangement = self._active_measure_arrangement()
        preview = getattr(self, "score_preview", None)
        if note is None or arrangement is None or preview is None:
            return
        clear_event_mark(
            self.project,
            source_sha256=preview.source_sha256,
            arrangement=arrangement.instrument,
            event_index=note.event_index,
        )
        self._update_live_selected_summary()
        self._draw_eof_tab()
        self._draw_eof_highway()

    def _eof_tab_clicked(self, event: tk.Event) -> None:
        arrangement = self._active_measure_arrangement()
        if arrangement is None:
            return super()._eof_tab_clicked(event)
        width = max(self.eof_tab_canvas.winfo_width(), 500)
        height = max(self.eof_tab_canvas.winfo_height(), 210)
        margin_left, margin_right = 58.0, 24.0
        top, bottom = 28.0, height - 28.0
        strings = max(string_count(arrangement), 1)
        usable_h = max(bottom - top, 1.0)
        string_index = int((event.y - top) / (usable_h / strings)) if top <= event.y <= bottom else -1
        window = self._live_window()
        usable_w = max(width - margin_left - margin_right, 1.0)
        click_time = window.start_seconds + min(max((event.x - margin_left) / usable_w, 0.0), 1.0) * window.span_seconds
        candidates = [n for n in arrangement.notes if n.string_index == string_index and abs(n.start_seconds - click_time) <= 0.10]
        if candidates:
            self._select_note(min(candidates, key=lambda n: abs(n.start_seconds - click_time)))
            return
        super()._eof_tab_clicked(event)

    def _eof_highway_clicked(self, event: tk.Event) -> None:
        arrangement = self._active_measure_arrangement()
        if arrangement is None:
            return super()._eof_highway_clicked(event)
        projected = sorted(highway_notes(arrangement, self._live_window()), key=lambda item: item.progress, reverse=True)
        # Existing EOF renderer appends one hit rectangle for every positioned projected note
        # in this same order. Zip the model identity back onto those tested hit boxes.
        positioned = [p for p in projected if p.note.string_index is not None and p.note.string_index < string_count(arrangement)]
        for hit, item in zip(reversed(self._eof_highway_hits), reversed(positioned)):
            x1, y1, x2, y2, _when = hit
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._select_note(item.note)
                return
        super()._eof_highway_clicked(event)

    def _draw_eof_tab(self) -> None:
        super()._draw_eof_tab()
        note = self._selected_note()
        arrangement = self._active_measure_arrangement()
        if note is None or arrangement is None or note.string_index is None:
            return
        canvas = self.eof_tab_canvas
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 210)
        margin_left, margin_right = 58.0, 24.0
        top, bottom = 28.0, height - 28.0
        strings = max(string_count(arrangement), 1)
        window = self._live_window()
        if not (window.start_seconds <= note.start_seconds <= window.end_seconds):
            return
        x = margin_left + time_fraction(note.start_seconds, window) * max(width - margin_left - margin_right, 1.0)
        y = top + (note.string_index + 0.5) * max(bottom - top, 1.0) / strings
        canvas.create_rectangle(x - 13, y - 16, x + 13, y + 16, outline=PALETTE.accent_hover, width=3)
