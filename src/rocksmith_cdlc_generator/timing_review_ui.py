from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .song_workspace_playback_ui import PlaybackSongWorkspaceWindow
from .timing_review import (
    ReviewedTiming,
    load_reviewed_timing,
    nudge_reviewed_beat,
    promote_reviewed_timing,
    refit_between_locked_anchors,
    set_anchor_locked,
    set_reviewed_beat_time,
)


class TimingReviewSongWorkspaceWindow(PlaybackSongWorkspaceWindow):
    """Interactive timing-review layer on top of synchronized Song Workspace playback."""

    def __init__(self, parent: tk.Misc, project: Path, *, run_callback=None) -> None:
        self.reviewed_timing: ReviewedTiming | None = None
        self._loop_start: float | None = None
        self._loop_end: float | None = None
        super().__init__(parent, project, run_callback=run_callback)
        self.bind("<space>", lambda _event: self._play_pause())

    def set_project(self, project: Path) -> None:
        self.reviewed_timing = None
        self._loop_start = None
        self._loop_end = None
        super().set_project(project)

    def _build_timeline(self) -> None:
        super()._build_timeline()

        review = ttk.LabelFrame(self.timeline_tab, text="Timing review", padding=8)
        review.pack(fill="x", pady=(8, 0))

        self.speed_var = tk.StringVar(value="100%")
        ttk.Label(review, text="Speed").pack(side="left")
        speed = ttk.Combobox(
            review,
            textvariable=self.speed_var,
            values=("50%", "75%", "100%"),
            state="readonly",
            width=6,
        )
        speed.pack(side="left", padx=(4, 10))
        speed.bind("<<ComboboxSelected>>", lambda _event: self._set_speed())

        self.click_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(review, text="Variable-tempo click", variable=self.click_var, command=self._set_click).pack(side="left", padx=(0, 12))

        ttk.Button(review, text="Loop start", command=self._set_loop_start).pack(side="left")
        ttk.Button(review, text="Loop end", command=self._set_loop_end).pack(side="left", padx=(4, 0))
        ttk.Button(review, text="Clear loop", command=self._clear_loop).pack(side="left", padx=(4, 12))

        ttk.Separator(review, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(review, text="−10 ms", command=lambda: self._nudge(-0.010)).pack(side="left")
        ttk.Button(review, text="−1 ms", command=lambda: self._nudge(-0.001)).pack(side="left", padx=(3, 0))
        ttk.Button(review, text="+1 ms", command=lambda: self._nudge(0.001)).pack(side="left", padx=(3, 0))
        ttk.Button(review, text="+10 ms", command=lambda: self._nudge(0.010)).pack(side="left", padx=(3, 6))
        ttk.Button(review, text="Exact…", command=self._set_exact).pack(side="left")
        self.lock_button = ttk.Button(review, text="Lock anchor", command=self._toggle_lock)
        self.lock_button.pack(side="left", padx=(4, 0))
        ttk.Button(review, text="Refit between locks", command=self._refit).pack(side="left", padx=(4, 0))
        ttk.Button(review, text="Promote reviewed timing", command=self._promote).pack(side="right")

        self.timing_review_var = tk.StringVar(value="Select a beat on the timeline to review timing.")
        ttk.Label(self.timeline_tab, textvariable=self.timing_review_var, wraplength=1200).pack(anchor="w", pady=(5, 0))

    def refresh(self) -> None:
        super().refresh()
        try:
            self.reviewed_timing = load_reviewed_timing(self.project, create=False)
        except FileNotFoundError:
            self.reviewed_timing = None
        except Exception as exc:
            self.reviewed_timing = None
            if hasattr(self, "timing_review_var"):
                self.timing_review_var.set(f"Reviewed timing unavailable: {exc}")
        self._configure_transport_review()
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _configure_transport_review(self) -> None:
        if self.transport is None or self.snapshot is None:
            return
        beat_times = (
            [anchor.reviewed_time_seconds for anchor in self.reviewed_timing.anchors]
            if self.reviewed_timing is not None
            else list(self.snapshot.timeline.beat_times)
        )
        self.transport.configure_click(beat_times, enabled=self.click_var.get())
        if self._loop_start is not None and self._loop_end is not None:
            try:
                self.transport.set_loop(self._loop_start, self._loop_end)
            except ValueError:
                self._clear_loop()

    def _set_speed(self) -> None:
        if self.transport is None:
            return
        rate = {"50%": 0.5, "75%": 0.75, "100%": 1.0}[self.speed_var.get()]
        try:
            self.transport.set_playback_rate(rate)
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)

    def _set_click(self) -> None:
        self._configure_transport_review()

    def _cursor_time(self) -> float:
        return max(0.0, float(self._selected_time or 0.0))

    def _set_loop_start(self) -> None:
        self._loop_start = self._cursor_time()
        if self._loop_end is not None and self._loop_end <= self._loop_start:
            self._loop_end = None
        self._apply_loop()

    def _set_loop_end(self) -> None:
        end = self._cursor_time()
        if self._loop_start is None:
            messagebox.showinfo("Song Workspace", "Set the loop start first.", parent=self)
            return
        if end <= self._loop_start:
            messagebox.showwarning("Song Workspace", "Loop end must be after loop start.", parent=self)
            return
        self._loop_end = end
        self._apply_loop()

    def _apply_loop(self) -> None:
        if self.transport is not None and self._loop_start is not None and self._loop_end is not None:
            try:
                self.transport.set_loop(self._loop_start, self._loop_end)
            except ValueError as exc:
                messagebox.showwarning("Song Workspace", str(exc), parent=self)
        self._draw_timeline()

    def _clear_loop(self) -> None:
        self._loop_start = None
        self._loop_end = None
        if self.transport is not None:
            self.transport.clear_loop()
        self._draw_timeline()

    def _nearest_beat_index(self) -> int | None:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.timeline.beat_times:
            return None
        when = self._cursor_time()
        times = (
            [anchor.reviewed_time_seconds for anchor in self.reviewed_timing.anchors]
            if self.reviewed_timing is not None
            else list(snapshot.timeline.beat_times)
        )
        return min(range(len(times)), key=lambda index: abs(times[index] - when))

    def _ensure_review(self) -> ReviewedTiming:
        review = load_reviewed_timing(self.project, create=True)
        self.reviewed_timing = review
        return review

    def _nudge(self, delta: float) -> None:
        index = self._nearest_beat_index()
        if index is None:
            return
        try:
            self.reviewed_timing = nudge_reviewed_beat(self.project, index, delta)
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self._selected_time = self.reviewed_timing.anchors[index].reviewed_time_seconds
        self._configure_transport_review()
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _set_exact(self) -> None:
        index = self._nearest_beat_index()
        if index is None:
            return
        review = self._ensure_review()
        current = review.anchors[index].reviewed_time_seconds
        value = simpledialog.askfloat(
            "Exact beat time",
            f"Reviewed timestamp for beat {index + 1} (seconds):",
            initialvalue=current,
            minvalue=0.0,
            parent=self,
        )
        if value is None:
            return
        try:
            self.reviewed_timing = set_reviewed_beat_time(self.project, index, value)
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self._selected_time = value
        self._configure_transport_review()
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _toggle_lock(self) -> None:
        index = self._nearest_beat_index()
        if index is None:
            return
        review = self._ensure_review()
        try:
            self.reviewed_timing = set_anchor_locked(self.project, index, not review.anchors[index].locked)
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _refit(self) -> None:
        index = self._nearest_beat_index()
        if index is None:
            return
        try:
            self.reviewed_timing = refit_between_locked_anchors(self.project, index)
        except Exception as exc:
            messagebox.showwarning("Song Workspace", str(exc), parent=self)
            return
        self._configure_transport_review()
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _promote(self) -> None:
        if not messagebox.askyesno(
            "Promote reviewed timing",
            "Mark the current reviewed beat timing as human-confirmed? Raw detector timing will remain unchanged.",
            parent=self,
        ):
            return
        try:
            self.reviewed_timing, output = promote_reviewed_timing(self.project)
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self.timing_review_var.set(f"Reviewed timing promoted: {output.name}. Raw tempo analysis was preserved.")
        self._draw_timeline()

    def _timeline_clicked(self, event: tk.Event) -> None:
        super()._timeline_clicked(event)
        self._refresh_selected_beat_text()

    def _refresh_selected_beat_text(self) -> None:
        if not hasattr(self, "timing_review_var"):
            return
        index = self._nearest_beat_index()
        if index is None or self.snapshot is None:
            self.timing_review_var.set("No analyzed beats are available yet.")
            return
        review = self.reviewed_timing
        raw_time = self.snapshot.timeline.beat_times[index]
        if review is None:
            self.lock_button.configure(text="Lock anchor")
            self.timing_review_var.set(
                f"Beat {index + 1}: raw {raw_time:.3f}s · not edited. Nudge or lock to begin a reviewed timing layer."
            )
            return
        anchor = review.anchors[index]
        delta_ms = (anchor.reviewed_time_seconds - anchor.original_time_seconds) * 1000.0
        self.lock_button.configure(text="Unlock anchor" if anchor.locked else "Lock anchor")
        state = "LOCKED" if anchor.locked else "edited/reviewable"
        confirmed = " · promoted" if review.human_confirmed else ""
        self.timing_review_var.set(
            f"Beat {index + 1}: {anchor.reviewed_time_seconds:.3f}s ({delta_ms:+.1f} ms from raw) · {state}{confirmed}"
        )

    def _draw_timeline(self) -> None:
        super()._draw_timeline()
        if not hasattr(self, "timeline_canvas") or self.snapshot is None:
            return
        canvas = self.timeline_canvas
        width = max(canvas.winfo_width(), 240)
        _height = max(canvas.winfo_height(), 320)
        start, end = self._view_bounds()

        if self._loop_start is not None and self._loop_end is not None:
            left = max(self._loop_start, start)
            right = min(self._loop_end, end)
            if right > left:
                x1 = self._timeline_x(left, width, self.snapshot.duration_seconds)
                x2 = self._timeline_x(right, width, self.snapshot.duration_seconds)
                canvas.create_rectangle(x1, 20, x2, 205, stipple="gray25", outline="")
                canvas.create_text((x1 + x2) / 2, 18, text="LOOP", anchor="s")

        if self.reviewed_timing is not None:
            for anchor in self.reviewed_timing.anchors:
                when = anchor.reviewed_time_seconds
                if when < start or when > end:
                    continue
                x = self._timeline_x(when, width, self.snapshot.duration_seconds)
                canvas.create_line(x, 210, x, 244, width=2 if anchor.locked else 1, dash=() if anchor.locked else (2, 2))
                if anchor.locked:
                    canvas.create_text(x, 207, text="◆", anchor="s")
