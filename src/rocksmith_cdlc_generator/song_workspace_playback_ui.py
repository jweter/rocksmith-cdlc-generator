from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .audio_playback import PlaybackUnavailable, ProjectAudioTransport
from .song_workspace_ui import SongWorkspaceWindow
from .waveform_cache import WaveformEnvelope, load_or_build_waveform


class PlaybackSongWorkspaceWindow(SongWorkspaceWindow):
    """Song Workspace with synchronized local playback and waveform navigation."""

    def __init__(self, parent: tk.Misc, project: Path, *, run_callback=None) -> None:
        self.transport: ProjectAudioTransport | None = None
        self.waveform: WaveformEnvelope | None = None
        self._media_project: Path | None = None
        self._view_start = 0.0
        self._zoom = 1.0
        self._playback_after_id: str | None = None
        super().__init__(parent, project, run_callback=run_callback)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(80, self._poll_playback)

    def set_project(self, project: Path) -> None:
        self._close_media()
        self._view_start = 0.0
        self._zoom = 1.0
        if hasattr(self, "zoom_var"):
            self.zoom_var.set("1×")
        super().set_project(project)

    def destroy(self) -> None:
        if self._playback_after_id is not None:
            try:
                self.after_cancel(self._playback_after_id)
            except tk.TclError:
                pass
            self._playback_after_id = None
        self._close_media()
        super().destroy()

    def _close_media(self) -> None:
        if self.transport is not None:
            try:
                self.transport.close()
            except Exception:
                pass
        self.transport = None
        self.waveform = None
        self._media_project = None

    def _build_timeline(self) -> None:
        transport = ttk.Frame(self.timeline_tab)
        transport.pack(fill="x", pady=(0, 6))
        self.play_button = ttk.Button(transport, text="▶ Play", command=self._play_pause)
        self.play_button.pack(side="left")
        ttk.Button(transport, text="■ Stop", command=self._stop).pack(side="left", padx=(6, 0))
        ttk.Button(transport, text="◀ 5s", command=lambda: self._seek_relative(-5.0)).pack(side="left", padx=(12, 0))
        ttk.Button(transport, text="5s ▶", command=lambda: self._seek_relative(5.0)).pack(side="left", padx=(6, 0))

        self._build_transport_extra(transport)

        self.playback_time_var = tk.StringVar(value="0:00.00 / 0:00.00")
        ttk.Label(transport, textvariable=self.playback_time_var, font=("Segoe UI", 10, "bold")).pack(side="left", padx=14)

        ttk.Button(transport, text="Pan ◀", command=lambda: self._pan(-0.25)).pack(side="right", padx=(4, 0))
        ttk.Button(transport, text="Pan ▶", command=lambda: self._pan(0.25)).pack(side="right", padx=(4, 0))
        ttk.Button(transport, text="Zoom −", command=lambda: self._change_zoom(0.5)).pack(side="right", padx=(12, 0))
        ttk.Button(transport, text="Zoom +", command=lambda: self._change_zoom(2.0)).pack(side="right", padx=(4, 0))
        self.zoom_var = tk.StringVar(value="1×")
        ttk.Label(transport, textvariable=self.zoom_var, width=5, anchor="center").pack(side="right")

        seek_row = ttk.Frame(self.timeline_tab)
        seek_row.pack(fill="x", pady=(0, 6))
        self.seek_var = tk.DoubleVar(value=0.0)
        self.seek_scale = ttk.Scale(
            seek_row,
            from_=0.0,
            to=1.0,
            variable=self.seek_var,
            command=self._seek_scale_changed,
        )
        self.seek_scale.pack(side="left", fill="x", expand=True)
        self.media_status_var = tk.StringVar(value="Audio preview becomes available after normalization.")
        ttk.Label(seek_row, textvariable=self.media_status_var, width=42, anchor="e").pack(side="right", padx=(12, 0))

        toolbar = ttk.Frame(self.timeline_tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, textvariable=self.timeline_summary_var).pack(side="left")
        ttk.Label(toolbar, textvariable=self.timeline_cursor_var).pack(side="right")

        self.timeline_canvas = tk.Canvas(self.timeline_tab, height=430, highlightthickness=1)
        self.timeline_canvas.pack(fill="both", expand=True)
        self.timeline_canvas.bind("<Configure>", lambda _event: self._draw_timeline())
        self.timeline_canvas.bind("<Button-1>", self._timeline_clicked)
        self.timeline_canvas.bind("<MouseWheel>", self._mousewheel_zoom)

        legend = ttk.Label(
            self.timeline_tab,
            text=(
                "Waveform and playhead use the normalized project audio. Beat markers, reviewed shared-timeline anchors, "
                "and validation findings share the same clock. Click the timeline to seek. Mouse wheel zooms around the cursor."
            ),
            wraplength=1200,
        )
        legend.pack(anchor="w", pady=(8, 0))

    def _build_transport_extra(self, transport: ttk.Frame) -> None:
        """Hook for subclasses to add controls into the transport row.

        Called after the seek buttons and before the elapsed/duration time label, so
        anything added here reads as directly associated with Play/Stop -- see the
        #305 Product Reality finding that review aids placed elsewhere in dense
        timing-edit controls were easy to miss. The base window adds nothing here.
        """

    def refresh(self) -> None:
        super().refresh()
        self._ensure_media()
        self._sync_media_controls()
        self._draw_timeline()

    def _ensure_media(self) -> None:
        if self._media_project == self.project and self.transport is not None and self.waveform is not None:
            return
        self._close_media()
        try:
            waveform = load_or_build_waveform(self.project)
            transport = ProjectAudioTransport(self.project)
        except FileNotFoundError:
            self.media_status_var.set("Run normalization to enable waveform + playback")
            return
        except (OSError, ValueError, PlaybackUnavailable) as exc:
            self.media_status_var.set(f"Audio preview unavailable: {exc}")
            return
        self.waveform = waveform
        self.transport = transport
        self._media_project = self.project
        self.seek_scale.configure(to=max(transport.duration_seconds, 0.001))
        self.media_status_var.set(
            f"{transport.sample_rate_hz / 1000:.1f} kHz · {transport.channels} ch · normalized PCM"
        )

    def _sync_media_controls(self) -> None:
        duration = self.snapshot.duration_seconds if self.snapshot is not None else 0.0
        position = self.transport.position_seconds if self.transport is not None else (self._selected_time or 0.0)
        self.seek_var.set(min(position, duration))
        self.playback_time_var.set(f"{self._format_time(position)} / {self._format_time(duration)}")
        self.play_button.configure(text="❚❚ Pause" if self.transport is not None and self.transport.playing else "▶ Play")

    def _play_pause(self) -> None:
        self._ensure_media()
        if self.transport is None:
            messagebox.showinfo(
                "Song Workspace",
                "Normalize the project audio first. The normal automatic workflow does this before timing analysis.",
                parent=self,
            )
            return
        try:
            if self.transport.playing:
                self.transport.pause()
            else:
                if self._selected_time is not None and abs(self.transport.position_seconds - self._selected_time) > 0.05:
                    self.transport.seek(self._selected_time)
                self.transport.play()
        except (OSError, ValueError, PlaybackUnavailable) as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
        self._sync_media_controls()

    def _stop(self) -> None:
        if self.transport is not None:
            self.transport.stop()
        self._selected_time = 0.0
        self._view_start = 0.0
        self.timeline_cursor_var.set("Cursor: 0:00.00 (0.000s)")
        self._sync_media_controls()
        self._draw_timeline()

    def _seek_relative(self, delta: float) -> None:
        current = self.transport.position_seconds if self.transport is not None else (self._selected_time or 0.0)
        self._seek_to(current + delta)

    def _seek_to(self, seconds: float) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        bounded = min(max(float(seconds), 0.0), snapshot.duration_seconds)
        self._selected_time = bounded
        if self.transport is not None:
            try:
                self.transport.seek(bounded)
            except (OSError, ValueError, PlaybackUnavailable) as exc:
                self.media_status_var.set(f"Seek failed: {exc}")
        self._keep_time_visible(bounded)
        self.timeline_cursor_var.set(f"Cursor: {self._format_time(bounded)} ({bounded:.3f}s)")
        self._sync_media_controls()
        self._draw_timeline()

    def _seek_scale_changed(self, raw: str) -> None:
        try:
            value = float(raw)
        except ValueError:
            return
        # ttk.Scale sends callbacks during programmatic updates on some Tk builds. Ignore
        # tiny feedback movements around the live playback position.
        current = self.transport.position_seconds if self.transport is not None else (self._selected_time or 0.0)
        if abs(value - current) < 0.08:
            return
        self._seek_to(value)

    def _poll_playback(self) -> None:
        try:
            if self.transport is not None:
                position = self.transport.position_seconds
                if self.transport.playing:
                    self._selected_time = position
                    self._keep_time_visible(position)
                    self.timeline_cursor_var.set(f"Playhead: {self._format_time(position)} ({position:.3f}s)")
                    self._draw_timeline()
                self._sync_media_controls()
        finally:
            if self.winfo_exists():
                self._playback_after_id = self.after(50, self._poll_playback)

    def _visible_span(self) -> float:
        if self.snapshot is None:
            return 1.0
        return max(self.snapshot.duration_seconds / self._zoom, 0.05)

    def _view_bounds(self) -> tuple[float, float]:
        if self.snapshot is None:
            return (0.0, 1.0)
        duration = self.snapshot.duration_seconds
        span = min(self._visible_span(), duration if duration > 0 else 1.0)
        start = min(max(self._view_start, 0.0), max(duration - span, 0.0))
        return start, min(start + span, duration)

    def _keep_time_visible(self, seconds: float) -> None:
        if self.snapshot is None or self._zoom <= 1.0:
            self._view_start = 0.0
            return
        start, end = self._view_bounds()
        span = max(end - start, 0.05)
        margin = span * 0.12
        if seconds < start + margin or seconds > end - margin:
            self._view_start = min(
                max(seconds - span / 2, 0.0),
                max(self.snapshot.duration_seconds - span, 0.0),
            )

    def _change_zoom(self, factor: float, *, focus_time: float | None = None) -> None:
        if self.snapshot is None:
            return
        old_start, old_end = self._view_bounds()
        old_span = max(old_end - old_start, 0.05)
        focus = focus_time if focus_time is not None else (self._selected_time if self._selected_time is not None else (old_start + old_end) / 2)
        focus_fraction = min(max((focus - old_start) / old_span, 0.0), 1.0)
        self._zoom = min(max(self._zoom * factor, 1.0), 64.0)
        new_span = min(self.snapshot.duration_seconds / self._zoom, self.snapshot.duration_seconds)
        self._view_start = focus - (new_span * focus_fraction)
        self._view_start = min(max(self._view_start, 0.0), max(self.snapshot.duration_seconds - new_span, 0.0))
        self.zoom_var.set(f"{self._zoom:g}×")
        self._draw_timeline()

    def _pan(self, fraction: float) -> None:
        if self.snapshot is None:
            return
        span = self._visible_span()
        self._view_start = min(
            max(self._view_start + span * fraction, 0.0),
            max(self.snapshot.duration_seconds - span, 0.0),
        )
        self._draw_timeline()

    def _mousewheel_zoom(self, event: tk.Event) -> None:
        if self.snapshot is None:
            return
        focus = self._time_from_canvas_x(float(event.x))
        self._change_zoom(2.0 if event.delta > 0 else 0.5, focus_time=focus)

    def _timeline_x(self, time_seconds: float, width: float, duration: float) -> float:
        margin = 55.0
        usable = max(width - (2 * margin), 1.0)
        start, end = self._view_bounds()
        span = max(end - start, 0.001)
        return margin + ((time_seconds - start) / span) * usable

    def _time_from_canvas_x(self, x: float) -> float:
        width = max(self.timeline_canvas.winfo_width(), 200)
        margin = 55.0
        usable = max(width - 2 * margin, 1.0)
        fraction = min(max((x - margin) / usable, 0.0), 1.0)
        start, end = self._view_bounds()
        return start + fraction * (end - start)

    def _timeline_clicked(self, event: tk.Event) -> None:
        self._seek_to(self._time_from_canvas_x(float(event.x)))

    def _draw_timeline(self) -> None:
        canvas = self.timeline_canvas
        canvas.delete("all")
        snapshot = self.snapshot
        if snapshot is None:
            return

        width = max(canvas.winfo_width(), 240)
        height = max(canvas.winfo_height(), 320)
        start, end = self._view_bounds()
        span = max(end - start, 0.001)
        margin = 55
        waveform_top = 30
        waveform_bottom = 185
        beat_y = 225
        anchor_y = 285
        review_y = height - 70

        # Waveform lane.
        canvas.create_text(8, (waveform_top + waveform_bottom) / 2, text="Audio", anchor="w")
        center_y = (waveform_top + waveform_bottom) / 2
        canvas.create_line(margin, center_y, width - margin, center_y)
        if self.waveform is not None and self.waveform.bucket_count:
            bucket_seconds = self.waveform.bucket_frames / self.waveform.sample_rate_hz
            first = max(0, int(start / bucket_seconds) - 1)
            last = min(self.waveform.bucket_count, int(end / bucket_seconds) + 2)
            visible_count = max(last - first, 1)
            stride = max(1, visible_count // max(int(width - 2 * margin), 1))
            amplitude = (waveform_bottom - waveform_top) * 0.47
            for index in range(first, last, stride):
                when = min(index * bucket_seconds, snapshot.duration_seconds)
                x = self._timeline_x(when, width, snapshot.duration_seconds)
                low = self.waveform.minimums[index]
                high = self.waveform.maximums[index]
                canvas.create_line(x, center_y - high * amplitude, x, center_y - low * amplitude)
        else:
            canvas.create_text((margin + width - margin) / 2, center_y, text="Waveform available after normalization")

        for y, label in ((beat_y, "Beats"), (anchor_y, "Anchors"), (review_y, "Review")):
            canvas.create_line(margin, y, width - margin, y)
            canvas.create_text(8, y, text=label, anchor="w")

        # View-relative time grid.
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            when = start + span * fraction
            x = self._timeline_x(when, width, snapshot.duration_seconds)
            canvas.create_line(x, waveform_top, x, review_y + 18, dash=(2, 4))
            canvas.create_text(x, review_y + 28, text=self._format_time(when), anchor="n")

        beat_times = [when for when in snapshot.timeline.beat_times if start <= when <= end]
        stride = max(1, len(beat_times) // max(int((width - 2 * margin) // 4), 1))
        for index, when in enumerate(beat_times):
            if index % stride:
                continue
            x = self._timeline_x(when, width, snapshot.duration_seconds)
            canvas.create_line(x, beat_y - 8, x, beat_y + 8)

        for when in snapshot.timeline.shared_anchor_audio_times:
            if not start <= when <= end:
                continue
            x = self._timeline_x(when, width, snapshot.duration_seconds)
            canvas.create_oval(x - 4, anchor_y - 4, x + 4, anchor_y + 4, fill="black")

        for item in snapshot.review_queue:
            if item.time_seconds is None or not start <= item.time_seconds <= end:
                continue
            x = self._timeline_x(item.time_seconds, width, snapshot.duration_seconds)
            marker_height = 15 if item.severity == "FAIL" else 10
            canvas.create_line(x, review_y - marker_height, x, review_y + marker_height, width=2)

        if self._selected_time is not None and start <= self._selected_time <= end:
            x = self._timeline_x(self._selected_time, width, snapshot.duration_seconds)
            canvas.create_line(x, waveform_top - 6, x, review_y + 22, width=2)

        canvas.create_text(
            width - margin,
            12,
            text=f"View {self._format_time(start)} – {self._format_time(end)} · {self._zoom:g}×",
            anchor="e",
        )
