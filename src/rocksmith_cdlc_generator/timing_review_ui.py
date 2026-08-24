from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .score_timing_anchors import (
    ScoreTimingAnchorReview,
    ScoreTimingRefitPreview,
    build_score_timing_refit_preview,
    confirm_candidate_anchor,
    load_score_timing_anchor_review,
    mark_score_beat_at_recording_time,
    nearest_candidate_anchor,
)
from .score_timing_refit_review import (
    accept_score_timing_refit,
    load_current_score_timing_refit_acceptance,
)
from .shared_timeline import (
    SharedTimeline,
    build_shared_timeline_candidate,
    load_current_shared_timeline,
    promote_shared_timeline,
)
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


#: Kept as "Variable-tempo click" (not the packaged "Click Track · Audition Beat
#: Grid" display text) so the existing desktop_polish.polish_widget_tree text/style
#: promotion for this exact review-aid checkbox keeps matching it verbatim -- see
#: desktop_polish._REVIEW_AID_LABELS and docs/ui/desktop-theme-v1.md.
CLICK_TRACK_LABEL = "Variable-tempo click"

#: Short, always-visible caption explaining the control per the #305 Product
#: Reality request ("a concise tooltip explaining that it plays an audible pulse on
#: detected/reviewed beats so the user can judge alignment against the recording").
CLICK_TRACK_HELP_TEXT = "Plays an audible pulse on reviewed beats so you can judge alignment by ear."


def _unique_refit_points(preview: ScoreTimingRefitPreview) -> list:
    """Return bounded refit points once each, ordered by symbolic score beat."""
    by_beat = {}
    for region in preview.regions:
        for point in region.points:
            by_beat[point.source_beat_index] = point
    return [by_beat[index] for index in sorted(by_beat)]


def _refit_preview_summary(preview: ScoreTimingRefitPreview) -> str:
    return (
        f"Bounded refit preview: {len(preview.regions)} reviewed region(s), "
        f"{len(_unique_refit_points(preview))} score beats, "
        f"maximum adjustment {preview.max_abs_adjustment_seconds * 1000.0:.1f} ms."
    )


def _acceptance_matches_display(acceptance, candidate: SharedTimeline, preview: ScoreTimingRefitPreview) -> bool:
    """Return true only when acceptance matches the exact candidate and preview rendered in this window."""
    return acceptance.candidate == candidate and acceptance.preview == preview


class TimingReviewSongWorkspaceWindow(PlaybackSongWorkspaceWindow):
    """Interactive timing-review layer on top of synchronized Song Workspace playback."""

    def __init__(self, parent: tk.Misc, project: Path, *, run_callback=None) -> None:
        self.reviewed_timing: ReviewedTiming | None = None
        self.candidate_shared_timeline: SharedTimeline | None = None
        self.score_timing_anchor_review: ScoreTimingAnchorReview | None = None
        self.score_timing_refit_preview: ScoreTimingRefitPreview | None = None
        self._loop_start: float | None = None
        self._loop_end: float | None = None
        super().__init__(parent, project, run_callback=run_callback)
        self.bind("<space>", lambda _event: self._play_pause())

    def set_project(self, project: Path) -> None:
        self.reviewed_timing = None
        self.candidate_shared_timeline = None
        self.score_timing_anchor_review = None
        self.score_timing_refit_preview = None
        self._loop_start = None
        self._loop_end = None
        super().set_project(project)

    def _build_timeline(self) -> None:
        super()._build_timeline()

        # Product Reality feedback (#305) found the click/beat-grid audition toggle
        # highly effective for by-ear timing review but too easy to miss buried among
        # unrelated timing-edit controls. Anchor it directly beside Play/Stop instead,
        # with a short always-visible caption explaining what it does, so a first-time
        # user discovers it without scanning the whole Timing review section below.
        self.click_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.transport_row,
            text=CLICK_TRACK_LABEL,
            variable=self.click_var,
            command=self._set_click,
        ).pack(side="left", padx=(14, 4))
        ttk.Label(
            self.transport_row,
            text=CLICK_TRACK_HELP_TEXT,
            style="Muted.TLabel",
        ).pack(side="left", padx=(0, 4))

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
        ttk.Button(review, text="Confirm beat edits", command=self._confirm_beat_edits).pack(side="left", padx=(4, 0))
        self.shared_promote_button = ttk.Button(
            review,
            text="Promote shared song timing",
            command=self._promote_shared_timing,
        )
        self.shared_promote_button.pack(side="right")

        score_review = ttk.LabelFrame(self.timeline_tab, text="Score-aware anchors", padding=8)
        score_review.pack(fill="x", pady=(8, 0))
        self.confirm_score_anchor_button = ttk.Button(
            score_review,
            text="Confirm proposed score anchor",
            command=self._confirm_score_anchor,
        )
        self.confirm_score_anchor_button.pack(side="left")
        self.mark_score_anchor_button = ttk.Button(
            score_review,
            text="Mark score beat here…",
            command=self._mark_score_anchor_here,
        )
        self.mark_score_anchor_button.pack(side="left", padx=(6, 0))
        self.accept_score_refit_button = ttk.Button(
            score_review,
            text="Accept bounded refit review",
            command=self._accept_score_refit,
            state="disabled",
        )
        self.accept_score_refit_button.pack(side="left", padx=(6, 0))
        self.score_anchor_var = tk.StringVar(
            value="Sparse score anchors are review evidence only; they do not change or promote timing yet."
        )
        ttk.Label(score_review, textvariable=self.score_anchor_var, wraplength=760).pack(side="left", padx=(12, 0))

        self.timing_gate_var = tk.StringVar(
            value=(
                "Review the score-to-recording timing across representative song sections. "
                "Individual beat locks are correction tools, not a checklist."
            )
        )
        ttk.Label(
            self.timeline_tab,
            textvariable=self.timing_gate_var,
            wraplength=1200,
        ).pack(anchor="w", pady=(5, 0))

        self.timing_review_var = tk.StringVar(value="Select a beat on the timeline to review timing.")
        ttk.Label(self.timeline_tab, textvariable=self.timing_review_var, wraplength=1200).pack(anchor="w", pady=(5, 0))

    def refresh(self) -> None:
        super().refresh()
        if self.snapshot is None:
            return
        try:
            self.reviewed_timing = load_reviewed_timing(self.project, create=False)
        except FileNotFoundError:
            self.reviewed_timing = None
        except Exception as exc:
            self.reviewed_timing = None
            if hasattr(self, "timing_review_var"):
                self.timing_review_var.set(f"Reviewed timing unavailable: {exc}")
        self._configure_transport_review()
        self._refresh_timing_gate_guidance()
        self._refresh_score_anchor_review()
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

    def _confirm_beat_edits(self) -> None:
        if not messagebox.askyesno(
            "Confirm beat edits",
            (
                "Mark the current reviewed detector-beat timing as human-confirmed? "
                "This confirms beat-map edits only; it does not promote the shared Bass/Lead/Rhythm song timeline."
            ),
            parent=self,
        ):
            return
        try:
            self.reviewed_timing, output = promote_reviewed_timing(self.project)
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self.timing_review_var.set(
            f"Beat timing edits confirmed: {output.name}. Shared song timing still requires its separate promotion gate."
        )
        self._refresh_selected_beat_text()
        self._refresh_timing_gate_guidance()
        self._draw_timeline()

    def _confirm_score_anchor(self) -> None:
        candidate = self.candidate_shared_timeline
        if candidate is None:
            messagebox.showwarning("Song Workspace", "No validated score-timing candidate is available to review.", parent=self)
            return
        anchor = nearest_candidate_anchor(candidate, self._cursor_time())
        if anchor is None:
            messagebox.showwarning("Song Workspace", "The current timing candidate has no proposed score anchors.", parent=self)
            return
        if not messagebox.askyesno(
            "Confirm proposed score anchor",
            (
                f"Confirm score beat {anchor.source_beat_index + 1} at {anchor.audio_time_seconds:.3f}s as human review evidence? "
                "This records the correspondence only; it does not alter or promote timing."
            ),
            parent=self,
        ):
            return
        try:
            self.score_timing_anchor_review = confirm_candidate_anchor(
                self.project,
                anchor.source_beat_index,
                expected_candidate=candidate,
            )
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self._refresh_score_anchor_review()
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _mark_score_anchor_here(self) -> None:
        candidate = self.candidate_shared_timeline
        if candidate is None:
            messagebox.showwarning("Song Workspace", "No validated score-timing candidate is available to review.", parent=self)
            return
        nearest = nearest_candidate_anchor(candidate, self._cursor_time())
        initial = None if nearest is None else nearest.source_beat_index + 1
        beat_number = simpledialog.askinteger(
            "Mark score beat here",
            f"Which score beat occurs at the current recording cursor ({self._cursor_time():.3f}s)?",
            initialvalue=initial,
            minvalue=1,
            parent=self,
        )
        if beat_number is None:
            return
        try:
            self.score_timing_anchor_review = mark_score_beat_at_recording_time(
                self.project,
                beat_number - 1,
                self._cursor_time(),
                expected_candidate=candidate,
            )
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self._refresh_score_anchor_review()
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _accept_score_refit(self) -> None:
        candidate = self.candidate_shared_timeline
        preview = self.score_timing_refit_preview
        if candidate is None or preview is None:
            messagebox.showwarning(
                "Song Workspace",
                "At least two current human score anchors are required before a bounded refit can be reviewed.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Accept bounded score-timing refit",
            (
                _refit_preview_summary(preview)
                + " Accept this exact bounded proposal as human review evidence? "
                "This does not promote or alter the shared song timeline."
            ),
            parent=self,
        ):
            return
        try:
            accept_score_timing_refit(
                self.project,
                expected_candidate=candidate,
                expected_preview=preview,
            )
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self._refresh_score_anchor_review()
        self._refresh_selected_beat_text()
        self._draw_timeline()

    def _promote_shared_timing(self) -> None:
        if self.candidate_shared_timeline is None:
            messagebox.showwarning(
                "Song Workspace",
                "The current Bass score alignment is not validated for promotion. Refresh the project and resolve the timing guidance first.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Promote shared song timing",
            (
                "Accept the validated Bass score-to-recording alignment shown as score-anchor diamonds on the timeline as the shared "
                "song timeline for Bass, Lead, and Rhythm? You do not need to lock every detected beat. Individual beat locks/refits "
                "are optional correction tools. Sparse human score anchors and bounded refit acceptance remain review evidence only "
                "and do not modify this candidate yet."
            ),
            parent=self,
        ):
            return
        try:
            output = promote_shared_timeline(
                self.project,
                expected_candidate=self.candidate_shared_timeline,
            )
        except Exception as exc:
            messagebox.showerror("Song Workspace", str(exc), parent=self)
            return
        self.refresh()
        self.timing_gate_var.set(
            f"Shared song timing promoted: {output.name}. Bass, Lead, and Rhythm can now inherit it; run safe automatic steps to continue."
        )

    def _refresh_timing_gate_guidance(self) -> None:
        if not hasattr(self, "timing_gate_var") or not hasattr(self, "shared_promote_button"):
            return

        self.candidate_shared_timeline = None
        try:
            load_current_shared_timeline(self.project)
        except (OSError, ValueError):
            timeline_current = False
        else:
            timeline_current = True

        if timeline_current:
            self.shared_promote_button.configure(text="Shared timing promoted", state="disabled")
            self.timing_gate_var.set(
                "Shared song timing is promoted. Individual beat locks are optional correction tools, not required approvals. "
                "Use Run Safe Automatic Steps to continue building the arrangements."
            )
            return

        try:
            candidate = build_shared_timeline_candidate(self.project)
        except Exception as exc:
            self.shared_promote_button.configure(text="Promote shared song timing", state="disabled")
            self.timing_gate_var.set(
                "Shared timing cannot be promoted yet: " + str(exc)
            )
            return

        self.candidate_shared_timeline = candidate
        warning_text = f" · {len(candidate.warnings)} warning(s)" if candidate.warnings else ""
        self.shared_promote_button.configure(text="Promote shared song timing", state="normal")
        self.timing_gate_var.set(
            f"Validated candidate alignment: {len(candidate.anchors)} score anchors · confidence {candidate.confidence:.2f}" + warning_text + ". "
            "Score-anchor diamonds below show where symbolic score beats map into the recording. Play and inspect representative sections; "
            "you do not need to lock every detector beat. Promote only when this candidate alignment sounds and looks correct."
        )

    def _refresh_score_anchor_review(self) -> None:
        if not hasattr(self, "score_anchor_var"):
            return
        candidate = self.candidate_shared_timeline
        if candidate is None:
            self.score_timing_anchor_review = None
            self.score_timing_refit_preview = None
            self.confirm_score_anchor_button.configure(state="disabled")
            self.mark_score_anchor_button.configure(state="disabled")
            self.accept_score_refit_button.configure(text="Accept bounded refit review", state="disabled")
            self.score_anchor_var.set(
                "Score-aware anchor review is available when a validated unpromoted score-timing candidate is present."
            )
            return
        try:
            review = load_score_timing_anchor_review(self.project)
        except Exception as exc:
            self.score_timing_anchor_review = None
            self.score_timing_refit_preview = None
            self.confirm_score_anchor_button.configure(state="disabled")
            self.mark_score_anchor_button.configure(state="disabled")
            self.accept_score_refit_button.configure(text="Accept bounded refit review", state="disabled")
            self.score_anchor_var.set(f"Score-aware anchor evidence unavailable: {exc}")
            return
        self.score_timing_anchor_review = review
        self.confirm_score_anchor_button.configure(state="normal")
        self.mark_score_anchor_button.configure(state="normal")
        confirmed = sum(anchor.origin == "confirmed_candidate" for anchor in review.anchors)
        manual = sum(anchor.origin == "manual_cursor" for anchor in review.anchors)
        anchor_text = (
            f"Human score anchors: {len(review.anchors)} total ({confirmed} confirmed proposal, {manual} manually marked)."
        )
        if len(review.anchors) < 2:
            self.score_timing_refit_preview = None
            self.accept_score_refit_button.configure(text="Accept bounded refit review", state="disabled")
            self.score_anchor_var.set(
                anchor_text + " Add another human score anchor to create a bounded refit preview."
            )
            return
        try:
            preview = build_score_timing_refit_preview(self.project, expected_candidate=candidate)
        except Exception as exc:
            self.score_timing_refit_preview = None
            self.accept_score_refit_button.configure(text="Accept bounded refit review", state="disabled")
            self.score_anchor_var.set(anchor_text + f" Bounded refit preview unavailable: {exc}")
            return
        self.score_timing_refit_preview = preview
        acceptance_state = ""
        try:
            acceptance = load_current_score_timing_refit_acceptance(self.project)
        except FileNotFoundError:
            accepted = False
        except (OSError, ValueError):
            accepted = False
            acceptance_state = " Prior acceptance is stale; review the current preview again."
        else:
            accepted = _acceptance_matches_display(acceptance, candidate, preview)
            if not accepted:
                acceptance_state = " Prior acceptance is for a different current preview; review this displayed preview again."
        if accepted:
            self.accept_score_refit_button.configure(text="Bounded refit reviewed", state="disabled")
            acceptance_state = " This exact bounded refit is human-reviewed."
        else:
            self.accept_score_refit_button.configure(text="Accept bounded refit review", state="normal")
        self.score_anchor_var.set(
            anchor_text
            + " "
            + _refit_preview_summary(preview)
            + acceptance_state
            + " Review evidence only; shared timing is unchanged."
        )

    def _timeline_clicked(self, event: tk.Event) -> None:
        super()._timeline_clicked(event)
        self._refresh_selected_beat_text()

    def _nearest_refit_point_text(self) -> str:
        preview = getattr(self, "score_timing_refit_preview", None)
        if preview is None:
            return ""
        points = _unique_refit_points(preview)
        if not points:
            return ""
        cursor = self._cursor_time()
        point = min(
            points,
            key=lambda item: (abs(item.refit_time_seconds - cursor), item.source_beat_index),
        )
        adjustment_ms = (point.refit_time_seconds - point.candidate_time_seconds) * 1000.0
        return (
            f" · bounded refit: score beat {point.source_beat_index + 1} → {point.refit_time_seconds:.3f}s "
            f"({adjustment_ms:+.1f} ms vs candidate)"
        )

    def _nearest_candidate_anchor_text(self) -> str:
        candidate = self.candidate_shared_timeline
        if candidate is None:
            return self._nearest_refit_point_text()
        anchor = nearest_candidate_anchor(candidate, self._cursor_time())
        if anchor is None:
            return self._nearest_refit_point_text()
        delta = anchor.audio_time_seconds - self._cursor_time()
        reviewed = ""
        if self.score_timing_anchor_review is not None:
            human = next(
                (item for item in self.score_timing_anchor_review.anchors if item.source_beat_index == anchor.source_beat_index),
                None,
            )
            if human is not None:
                reviewed = f" · human anchor at {human.recording_time_seconds:.3f}s"
        return (
            f" · nearest score anchor: score beat {anchor.source_beat_index + 1} → "
            f"{anchor.audio_time_seconds:.3f}s ({delta:+.3f}s from cursor){reviewed}"
            + self._nearest_refit_point_text()
        )

    def _refresh_selected_beat_text(self) -> None:
        if not hasattr(self, "timing_review_var"):
            return
        index = self._nearest_beat_index()
        if index is None or self.snapshot is None:
            self.timing_review_var.set("No analyzed beats are available yet.")
            return
        candidate_text = self._nearest_candidate_anchor_text()
        review = self.reviewed_timing
        raw_time = self.snapshot.timeline.beat_times[index]
        if review is None:
            self.lock_button.configure(text="Lock anchor")
            self.timing_review_var.set(
                f"Beat {index + 1}: raw {raw_time:.3f}s · not edited. Nudge or lock only if this detector beat needs correction." + candidate_text
            )
            return
        anchor = review.anchors[index]
        delta_ms = (anchor.reviewed_time_seconds - anchor.original_time_seconds) * 1000.0
        self.lock_button.configure(text="Unlock anchor" if anchor.locked else "Lock anchor")
        state = "LOCKED" if anchor.locked else "edited/reviewable"
        confirmed = " · beat edits confirmed" if review.human_confirmed else ""
        self.timing_review_var.set(
            f"Beat {index + 1}: {anchor.reviewed_time_seconds:.3f}s ({delta_ms:+.1f} ms from raw) · {state}{confirmed}" + candidate_text
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

        if self.candidate_shared_timeline is not None:
            for anchor in self.candidate_shared_timeline.anchors:
                when = anchor.audio_time_seconds
                if when < start or when > end:
                    continue
                x = self._timeline_x(when, width, self.snapshot.duration_seconds)
                canvas.create_line(x, 250, x, 286, width=2, dash=(4, 2))
                canvas.create_text(x, 247, text="◇", anchor="s")

        if self.score_timing_refit_preview is not None:
            visible = [
                point
                for point in _unique_refit_points(self.score_timing_refit_preview)
                if start <= point.refit_time_seconds <= end and not point.human_anchor
            ]
            stride = max(1, (len(visible) + 199) // 200)
            for point in visible[::stride]:
                x = self._timeline_x(point.refit_time_seconds, width, self.snapshot.duration_seconds)
                canvas.create_line(x, 276, x, 286, width=1, dash=(1, 2))

        if self.score_timing_anchor_review is not None:
            for anchor in self.score_timing_anchor_review.anchors:
                when = anchor.recording_time_seconds
                if when < start or when > end:
                    continue
                x = self._timeline_x(when, width, self.snapshot.duration_seconds)
                canvas.create_line(x, 290, x, 318, width=2)
                canvas.create_text(x, 287, text="●", anchor="s")
