from __future__ import annotations

from time import perf_counter
import math
from pathlib import Path
from queue import SimpleQueue, Empty
from threading import Thread
import tkinter as tk
from tkinter import ttk

from .desktop_theme import PALETTE
from .eof_live_preview import highway_notes, string_count, time_fraction
from .human_review_marks import clear_event_mark, load_current_human_review_layer, mark_event
from .instrument_audio_spectrum import SpectrumSample, measure_spectrum
from .instrument_audio_focus import (
    FocusUnavailable, candidate_positions, focus_profile, midi_frequency, prepare_focused_audio,
)
from .audio_playback import PlaybackUnavailable
from .package_generation import invalidate_package_state


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
        self._focus_results: SimpleQueue = SimpleQueue()
        self._focus_active_job: tuple | None = None
        self._focus_ready: dict[tuple, Path] = {}
        self._focus_last_context: tuple | None = None
        self._focus_selected_mode = "Original"
        self._focus_notice: str | None = None
        self._spectrum_requested_key: tuple | None = None
        self._spectrum_job_running = False
        self._spectrum_next: tuple | None = None
        self._spectrum_results: SimpleQueue = SimpleQueue()
        self._spectrum_polling = False
        self._spectrum_data: SpectrumSample | None = None
        self._spectrum_note_midi: int | None = None
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

        # #563: this transport bar and the selected-note/chord review row used to pack
        # straight into live_box at full size regardless of arrangement availability --
        # unlike eof_measure_review_ui.py's own #563 fix, which only shrinks the two
        # canvases below (_set_eof_live_preview_compact) and leaves this mixin's own
        # additions untouched. live_review_content_frame/live_review_unavailable_label
        # are mutually exclusive and toggled by _update_live_review_availability(), the
        # same *_content_frame/*_unavailable_label pattern every other secondary
        # Arrangement Preview panel already uses.
        self.live_review_content_frame = ttk.Frame(live_box)
        self.live_review_unavailable_label = ttk.Label(
            live_box,
            text="Live review controls become available once an arrangement draft exists for the selected role.",
            wraplength=1120,
            justify="left",
            foreground=PALETTE.text_muted,
        )

        transport = ttk.Frame(live_box)
        transport.pack(fill="x", pady=(0, 6))
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

        review = ttk.LabelFrame(self.live_review_content_frame, text="Selected note / chord review", padding=6)
        review.pack(fill="x", pady=(0, 6))
        self.live_selected_var = tk.StringVar(value="Click a fret number or note block to select it. Empty space still seeks.")
        ttk.Label(review, textvariable=self.live_selected_var, wraplength=850).pack(side="left", fill="x", expand=True)
        ttk.Button(review, text="Mark questionable", command=lambda: self._mark_selected("questionable")).pack(side="right", padx=(6, 0))
        ttk.Button(review, text="Mark wrong", command=lambda: self._mark_selected("wrong")).pack(side="right", padx=(6, 0))
        ttk.Button(review, text="Clear mark", command=self._clear_selected_mark).pack(side="right", padx=(6, 0))

        # #787: Keep the audio-evidence controls immediately beside the selected
        # event inspector. It is only a listening tool; no preview action promotes
        # or edits authoritative score events.
        focus_box = ttk.LabelFrame(
            self.live_review_content_frame, text="Instrument Audio Evidence (listening EQ ≠ isolated stem)", padding=5
        )
        focus_box.pack(fill="x", pady=(0, 5))
        self.focus_status_var = tk.StringVar(value="Select a note to audition focused instrument audio.")
        ttk.Label(
            focus_box, textvariable=self.focus_status_var, wraplength=980,
            justify="left", foreground=PALETTE.text_muted,
        ).pack(anchor="w")
        # The bars are measured from real PCM at the selected event. Their energy
        # is relative and must never be interpreted as a separator or pitch proof.
        self.focus_spectrum_canvas = tk.Canvas(
            focus_box, height=61, background=PALETTE.canvas,
            highlightthickness=1, highlightbackground=PALETTE.border,
        )
        self.focus_spectrum_canvas.pack(fill="x", pady=(4, 1))
        self.focus_spectrum_canvas.bind(
            "<Configure>", lambda _event: self._draw_instrument_spectrum()
        )
        self._draw_instrument_spectrum()
        focus_buttons = ttk.Frame(focus_box)
        focus_buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(
            focus_buttons, text="Prepare tuned focus",
            command=self._prepare_instrument_focus,
        ).pack(side="left")
        ttk.Button(
            focus_buttons, text="Original mix",
            command=lambda: self._set_instrument_audio_source("Original"),
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            focus_buttons, text="Focused",
            command=lambda: self._set_instrument_audio_source("Focused"),
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            focus_buttons, text="Stem",
            command=lambda: self._set_instrument_audio_source("Stem"),
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            focus_buttons, text="Loop note",
            command=self._loop_selected_instrument_note,
        ).pack(side="left", padx=(12, 0))
        ttk.Button(
            focus_buttons, text="Clear loop",
            command=self._clear_instrument_audio_loop,
        ).pack(side="left", padx=(6, 0))

        self._update_live_review_availability()

    def _update_live_review_availability(self) -> None:
        """Show compact status text instead of full-size always-disabled controls.

        live_review_content_frame/live_review_unavailable_label are the only content
        packed into live_box before the (separately-managed) eof_tab_canvas, so
        toggling which one is packed never reorders the canvases below.
        """
        if not hasattr(self, "live_review_content_frame"):
            return
        if self._active_measure_arrangement() is not None:
            self.live_review_unavailable_label.pack_forget()
            self.live_review_content_frame.pack(fill="x", before=self.eof_tab_canvas)
        else:
            self.live_review_content_frame.pack_forget()
            self.live_review_unavailable_label.pack(fill="x", anchor="w", pady=(0, 6), before=self.eof_tab_canvas)

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
        self._update_live_review_availability()
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

    def _current_mark_map(self) -> dict[tuple[str, int], object]:
        preview = getattr(self, "score_preview", None)
        if preview is None:
            return {}
        layer = load_current_human_review_layer(self.project, preview.source_sha256)
        if layer is None:
            return {}
        return {(mark.arrangement, mark.event_index): mark for mark in layer.marks}

    def _update_live_selected_summary(self) -> None:
        if not hasattr(self, "live_selected_var"):
            return
        self._update_focus_context()
        note = self._selected_note()
        arrangement = self._active_measure_arrangement()
        if note is None or arrangement is None:
            self.live_selected_var.set("Click a fret number or note block to select it. Empty space still seeks.")
            return
        mark = self._current_mark_map().get((arrangement.instrument, note.event_index))
        mark_text = f" · HUMAN {mark.state.upper()}" if mark is not None else ""
        techniques = ", ".join(note.techniques) if note.techniques else "none"
        self.live_selected_var.set(
            f"{arrangement.instrument.title()} event {note.event_index} · {note.start_seconds:.3f}s · MIDI {note.midi} · "
            f"string {note.string_index + 1 if note.string_index is not None else '?'} · fret {note.fret if note.fret is not None else '?'} · "
            f"techniques {techniques} · trust {note.trust_class.value} · confidence {note.import_confidence:.2f}{mark_text}"
        )

    def _draw_instrument_spectrum(self) -> None:
        canvas = getattr(self, "focus_spectrum_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 200)
        data = self._spectrum_data
        if data is None:
            canvas.create_text(
                8, 25, anchor="w", text="Select a note to measure audio frequency energy.",
                fill=PALETTE.text_muted,
            )
            return
        frequencies = data.frequencies_hz
        values = data.relative_magnitudes
        n = len(values)
        plot_left, plot_right = 10, width - 10
        step = (plot_right - plot_left) / n
        for i, amplitude in enumerate(values):
            top = 43 - (max(0.0, min(1.0, amplitude)) * 37)
            x = plot_left + i * step
            canvas.create_rectangle(
                x, top, x + max(step - 1, 1), 43,
                fill=PALETTE.accent_hover, outline="",
            )
        if self._spectrum_note_midi is not None:
            target = midi_frequency(self._spectrum_note_midi)
            if frequencies[0] <= target <= frequencies[-1]:
                position = min(
                    range(n), key=lambda i: abs(math.log(frequencies[i] / target))
                )
                x = plot_left + (position + 0.5) * step
                canvas.create_line(x, 2, x, 44, fill=PALETTE.warning, dash=(3, 3))
        canvas.create_text(plot_left, 52, text=f"{frequencies[0]:.0f} Hz", anchor="w", fill=PALETTE.text_muted)
        canvas.create_text(plot_right, 52, text=f"{frequencies[-1]/1000:.1f} kHz", anchor="e", fill=PALETTE.text_muted)

    def _request_instrument_spectrum(self) -> None:
        note = self._selected_note()
        arrangement = self._active_measure_arrangement()
        transport = getattr(self, "transport", None)
        if note is None or arrangement is None or transport is None:
            self._spectrum_requested_key = None
            self._spectrum_data = None
            self._spectrum_note_midi = None
            self._draw_instrument_spectrum()
            return
        source = transport.preview_source_path
        center = min(transport.duration_seconds, note.start_seconds + 0.1)
        key = (
            str(Path(self.project).resolve()), arrangement.instrument,
            note.event_index, note.start_seconds, str(source),
        )
        if key == self._spectrum_requested_key:
            return
        self._spectrum_requested_key = key
        self._spectrum_data = None
        self._spectrum_note_midi = note.midi
        self._draw_instrument_spectrum()
        request = (key, source, center)
        if self._spectrum_job_running:
            # Keep only the newest pending selection; do not start unbounded DSP workers
            # while the user rapidly clicks through notes or switches sources.
            self._spectrum_next = request
            return
        self._launch_instrument_spectrum(request)

    def _launch_instrument_spectrum(self, request: tuple) -> None:
        key, source, center = request
        self._spectrum_job_running = True

        def worker() -> None:
            try:
                sample = measure_spectrum(source, center)
                self._spectrum_results.put((key, sample, None))
            except Exception as exc:
                self._spectrum_results.put((key, None, str(exc)[:180]))

        Thread(target=worker, name="instrument-review-spectrum", daemon=True).start()
        if not self._spectrum_polling:
            self._spectrum_polling = True
            self.after(125, self._poll_instrument_spectrum)

    def _poll_instrument_spectrum(self) -> None:
        try:
            key, sample, failure = self._spectrum_results.get_nowait()
        except Empty:
            if self.winfo_exists():
                self.after(125, self._poll_instrument_spectrum)
            return
        self._spectrum_job_running = False
        self._spectrum_polling = False
        if key == self._spectrum_requested_key:
            self._spectrum_data = sample
            self._draw_instrument_spectrum()
            if failure:
                self._focus_notice = f"Spectral display unavailable: {failure}"
        queued = self._spectrum_next
        self._spectrum_next = None
        if queued is not None and queued[0] == self._spectrum_requested_key:
            self._launch_instrument_spectrum(queued)

    def _instrument_focus_key(self) -> tuple | None:
        arrangement = self._active_measure_arrangement()
        tuning = getattr(arrangement, "tuning_midi", None) if arrangement is not None else None
        if arrangement is None or tuning is None:
            return None
        return (str(Path(self.project).resolve()), arrangement.instrument, tuple(tuning))

    def _update_focus_context(self) -> None:
        if not hasattr(self, "focus_status_var"):
            return
        arrangement = self._active_measure_arrangement()
        context = (
            self._instrument_focus_key(),
            id(getattr(self, "transport", None)),
        )
        if context != self._focus_last_context:
            self._focus_last_context = context
            self._focus_selected_mode = "Original"
            self._focus_notice = None
            # An instrument change must never leave a stale Bass stem playing
            # while the visible arrangement is Lead/Rhythm (or vice versa).
            transport = getattr(self, "transport", None)
            if transport is not None:
                try:
                    transport.set_preview_source(None)
                except (OSError, ValueError, PlaybackUnavailable):
                    pass
        note = self._selected_note()
        if arrangement is None:
            self.focus_status_var.set("Arrangement unavailable: no instrument evidence.")
        elif not getattr(arrangement, "tuning_midi", None):
            self.focus_status_var.set(
                f"{arrangement.instrument.title()}: confirmed tuning missing; only original audio is authoritative."
            )
        elif note is None:
            self.focus_status_var.set(
                f"{arrangement.instrument.title()}: select a note. Audio mode: {self._focus_selected_mode}."
            )
        else:
            hz = midi_frequency(note.midi)
            positions = candidate_positions(note.midi, arrangement.tuning_midi)
            positions_text = ", ".join(f"S{string + 1}/F{fret}" for string, fret in positions) or "none"
            self.focus_status_var.set(
                f"{arrangement.instrument.title()} event {note.event_index} · "
                f"MIDI {note.midi} ({hz:.1f} Hz) · possible positions {positions_text} · "
                f"mode {self._focus_selected_mode} · tuning-aware audition is not pitch proof"
            )
        if self._focus_notice:
            self.focus_status_var.set(f"{self.focus_status_var.get()} · {self._focus_notice}")
        self._request_instrument_spectrum()

    def _prepare_instrument_focus(self) -> None:
        key = self._instrument_focus_key()
        if key is None:
            self._focus_notice = "Cannot focus: a confirmed instrument tuning is required."
            self._update_focus_context()
            return
        if self._focus_active_job is not None:
            self._focus_notice = "A focus render is already running. Original playback remains available."
            self._update_focus_context()
            return
        self._focus_active_job = key
        self._focus_notice = "Preparing local focused audio off the UI thread…"
        self._update_focus_context()

        def worker() -> None:
            try:
                result = prepare_focused_audio(Path(key[0]), key[1], key[2])
                self._focus_results.put((key, result, None))
            except Exception as exc:  # Always return a terminal failure to Tk; never poll forever.
                self._focus_results.put((key, None, f"{type(exc).__name__}: {str(exc)[:220]}"))

        Thread(target=worker, name="instrument-focused-preview", daemon=True).start()
        self.after(125, self._poll_instrument_focus_result)

    def _poll_instrument_focus_result(self) -> None:
        try:
            key, path, failure = self._focus_results.get_nowait()
        except Empty:
            if self.winfo_exists():
                self.after(125, self._poll_instrument_focus_result)
            return
        self._focus_active_job = None
        if key != self._instrument_focus_key():
            self._update_focus_context()
            return
        if failure is not None:
            self._focus_notice = f"Focused preview unavailable: {failure}"
            self._update_focus_context()
            return
        assert path is not None
        self._focus_ready[key] = path
        self._focus_notice = None
        self._set_instrument_audio_source("Focused")

    def _set_instrument_audio_source(self, mode: str) -> None:
        # Reconcile any newly constructed transport/role before switching.
        self._ensure_media()
        self._update_focus_context()
        transport = getattr(self, "transport", None)
        if transport is None:
            self._focus_notice = "Normalize project audio to audition instruments."
            self._update_focus_context()
            return
        key = self._instrument_focus_key()
        if mode == "Original":
            source = None
        elif key is None:
            self._focus_notice = "Confirm instrument tuning before choosing an instrument preview."
            self._update_focus_context()
            return
        elif mode == "Focused":
            source = self._focus_ready.get(key)
            if source is None:
                self._focus_notice = "Choose Prepare tuned focus first; original audio is still available."
                self._update_focus_context()
                return
        elif mode == "Stem":
            role = key[1]
            source = Path(self.project) / "stems" / ("bass.wav" if role == "bass" else "guitar.wav")
            if not source.is_file():
                self._focus_notice = "No locally separated stem for this instrument. A frequency filter is not a stem."
                self._update_focus_context()
                return
        else:
            raise ValueError("Unknown audio-preview mode")
        try:
            transport.set_preview_source(source)
        except (OSError, ValueError, PlaybackUnavailable) as exc:
            self._focus_notice = f"{mode} audio is not sample-aligned: {exc}"
            self._update_focus_context()
            return
        self._focus_selected_mode = mode
        self._focus_notice = None
        self._update_focus_context()

    def _loop_selected_instrument_note(self) -> None:
        note = self._selected_note()
        transport = getattr(self, "transport", None)
        if note is None or transport is None:
            self._focus_notice = "Select a note after project audio is ready."
            self._update_focus_context()
            return
        start = max(0.0, note.start_seconds - 0.15)
        end = min(transport.duration_seconds, max(note.start_seconds + 0.35, note.start_seconds + note.duration_seconds + 0.15))
        if end <= start:
            return
        transport.set_loop(start, end)
        self._seek_to(start)
        if not transport.playing:
            try:
                transport.play()
            except (OSError, ValueError, PlaybackUnavailable) as exc:
                self._focus_notice = f"Note loop unavailable: {exc}"
                self._update_focus_context()

    def _clear_instrument_audio_loop(self) -> None:
        transport = getattr(self, "transport", None)
        if transport is not None:
            transport.clear_loop()

    def _revalidate_after_mark_change(self, arrangement: str) -> None:
        if arrangement in {"lead", "rhythm"}:
            from .guitar_validation import validate_guitar_project_to_disk

            validate_guitar_project_to_disk(self.project, arrangement=arrangement)
        elif arrangement == "bass":
            from .validation import validate_project_to_disk

            validate_project_to_disk(self.project)

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
        if state == "wrong":
            # A `wrong` mark now blocks packaging for this arrangement (see
            # validate_guitar_project/validate_project's human_mark_wrong FAIL item). A
            # package that was already staged/registered before this mark existed must
            # not keep reporting `safe_for_manual_installation: true` for content the
            # reviewer just rejected, so advance the package-generation token and remove
            # any stale staging directory/receipt before revalidating.
            invalidate_package_state(self.project)
        self._revalidate_after_mark_change(arrangement.instrument)
        self.refresh()

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
        self._revalidate_after_mark_change(arrangement.instrument)
        self.refresh()

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
        positioned = [p for p in projected if p.note.string_index is not None and p.note.string_index < string_count(arrangement)]
        for hit, item in zip(reversed(self._eof_highway_hits), reversed(positioned)):
            x1, y1, x2, y2, _when = hit
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._select_note(item.note)
                return
        super()._eof_highway_clicked(event)

    def _draw_eof_tab(self) -> None:
        super()._draw_eof_tab()
        arrangement = self._active_measure_arrangement()
        if arrangement is None:
            return
        canvas = self.eof_tab_canvas
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 210)
        margin_left, margin_right = 58.0, 24.0
        top, bottom = 28.0, height - 28.0
        strings = max(string_count(arrangement), 1)
        window = self._live_window()
        marks = self._current_mark_map()
        for note in arrangement.notes:
            mark = marks.get((arrangement.instrument, note.event_index))
            if mark is None or note.string_index is None or not (window.start_seconds <= note.start_seconds <= window.end_seconds):
                continue
            x = margin_left + time_fraction(note.start_seconds, window) * max(width - margin_left - margin_right, 1.0)
            y = top + (note.string_index + 0.5) * max(bottom - top, 1.0) / strings
            color = PALETTE.danger if mark.state == "wrong" else PALETTE.warning
            canvas.create_rectangle(x - 12, y - 15, x + 12, y + 15, outline=color, width=3)
            canvas.create_text(x + 14, y - 14, text="X" if mark.state == "wrong" else "?", anchor="sw", fill=color, font=("Segoe UI", 9, "bold"))

        note = self._selected_note()
        if note is None or note.string_index is None or not (window.start_seconds <= note.start_seconds <= window.end_seconds):
            return
        x = margin_left + time_fraction(note.start_seconds, window) * max(width - margin_left - margin_right, 1.0)
        y = top + (note.string_index + 0.5) * max(bottom - top, 1.0) / strings
        canvas.create_rectangle(x - 15, y - 18, x + 15, y + 18, outline=PALETTE.accent_hover, width=3)
