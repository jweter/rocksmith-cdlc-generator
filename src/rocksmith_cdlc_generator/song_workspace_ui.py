from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .song_workspace import SongWorkspaceSnapshot, WorkspaceReviewItem, build_song_workspace_snapshot


class SongWorkspaceWindow(tk.Toplevel):
    """Persistent project-focused authoring workspace for the Windows desktop app."""

    def __init__(
        self,
        parent: tk.Misc,
        project: Path,
        *,
        run_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project.expanduser().resolve()
        self.run_callback = run_callback
        self.snapshot: SongWorkspaceSnapshot | None = None
        self._selected_time: float | None = None

        self.title("Song Workspace — Rocksmith CDLC Generator")
        self.geometry("1380x880")
        self.minsize(1040, 700)

        self.health_var = tk.StringVar(value="Loading…")
        self.song_var = tk.StringVar(value="")
        self.project_var = tk.StringVar(value=str(self.project))
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="")
        self.next_action_var = tk.StringVar(value="")
        self.timeline_summary_var = tk.StringVar(value="")
        self.timeline_cursor_var = tk.StringVar(value="Cursor: —")
        self.source_summary_var = tk.StringVar(value="")
        self.review_detail_var = tk.StringVar(value="Select a review item to see details.")

        self._build_layout()
        self.after_idle(self.refresh)

    def set_project(self, project: Path) -> None:
        self.project = project.expanduser().resolve()
        self.project_var.set(str(self.project))
        self._selected_time = None
        self.refresh()

    def _build_layout(self) -> None:
        header = ttk.Frame(self, padding=(14, 12, 14, 8))
        header.pack(fill="x")
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, textvariable=self.song_var, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(title_box, textvariable=self.project_var).pack(anchor="w", pady=(2, 0))

        status_box = ttk.Frame(header)
        status_box.pack(side="right")
        ttk.Label(status_box, textvariable=self.health_var, font=("Segoe UI", 11, "bold")).pack(anchor="e")
        self.progress = ttk.Progressbar(status_box, variable=self.progress_var, maximum=100, length=260)
        self.progress.pack(anchor="e", pady=(5, 2))
        ttk.Label(status_box, textvariable=self.progress_text_var).pack(anchor="e")

        action = ttk.LabelFrame(self, text="Next best action", padding=10)
        action.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Label(action, textvariable=self.next_action_var, wraplength=1080).pack(side="left", fill="x", expand=True)
        if self.run_callback is not None:
            ttk.Button(action, text="Run Safe Automatic Steps", command=self.run_callback).pack(side="right", padx=(10, 0))
        ttk.Button(action, text="Refresh", command=self.refresh).pack(side="right", padx=(10, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self.overview_tab = ttk.Frame(self.notebook, padding=12)
        self.timeline_tab = ttk.Frame(self.notebook, padding=12)
        self.arrangements_tab = ttk.Frame(self.notebook, padding=12)
        self.review_tab = ttk.Frame(self.notebook, padding=12)
        self.sources_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.overview_tab, text="Overview")
        self.notebook.add(self.timeline_tab, text="Timeline")
        self.notebook.add(self.arrangements_tab, text="Arrangements")
        self.notebook.add(self.review_tab, text="Review Queue")
        self.notebook.add(self.sources_tab, text="Sources")

        self._build_overview()
        self._build_timeline()
        self._build_arrangements()
        self._build_review_queue()
        self._build_sources()

    def _build_overview(self) -> None:
        summary = ttk.Frame(self.overview_tab)
        summary.pack(fill="x")
        self.overview_vars = {
            "recording": tk.StringVar(value="Recording: —"),
            "score": tk.StringVar(value="Score: —"),
            "timeline": tk.StringVar(value="Shared timeline: —"),
            "review": tk.StringVar(value="Review queue: —"),
        }
        for column, (key, label) in enumerate(
            (
                ("recording", "Recording"),
                ("score", "Complete score"),
                ("timeline", "Shared timing"),
                ("review", "Review state"),
            )
        ):
            box = ttk.LabelFrame(summary, text=label, padding=10)
            box.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0), pady=(0, 10))
            ttk.Label(box, textvariable=self.overview_vars[key], wraplength=280).pack(anchor="w")
            summary.columnconfigure(column, weight=1)

        steps_box = ttk.LabelFrame(self.overview_tab, text="Project progress", padding=10)
        steps_box.pack(fill="both", expand=True)
        self.overview_tree = ttk.Treeview(
            steps_box,
            columns=("role", "mapping", "draft", "validation", "export"),
            show="headings",
            height=8,
        )
        headings = (
            ("role", "Arrangement", 130),
            ("mapping", "Score mapping", 220),
            ("draft", "Draft", 140),
            ("validation", "Validation", 170),
            ("export", "Rocksmith XML", 150),
        )
        for key, title, width in headings:
            self.overview_tree.heading(key, text=title)
            self.overview_tree.column(key, width=width, anchor="w")
        self.overview_tree.pack(fill="both", expand=True)

    def _build_timeline(self) -> None:
        toolbar = ttk.Frame(self.timeline_tab)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, textvariable=self.timeline_summary_var).pack(side="left")
        ttk.Label(toolbar, textvariable=self.timeline_cursor_var).pack(side="right")

        self.timeline_canvas = tk.Canvas(self.timeline_tab, height=360, highlightthickness=1)
        self.timeline_canvas.pack(fill="both", expand=True)
        self.timeline_canvas.bind("<Configure>", lambda _event: self._draw_timeline())
        self.timeline_canvas.bind("<Button-1>", self._timeline_clicked)

        legend = ttk.Label(
            self.timeline_tab,
            text=(
                "Top lane: detected beats. Middle lane: reviewed shared-timeline anchors. "
                "Bottom lane: validation/review events. Click anywhere to place a review cursor."
            ),
            wraplength=1200,
        )
        legend.pack(anchor="w", pady=(8, 0))

    def _build_arrangements(self) -> None:
        intro = ttk.Label(
            self.arrangements_tab,
            text=(
                "Bass, Lead, and Rhythm remain separate arrangements, but score mapping and timing authority are visible together here. "
                "A present-but-not-current guitar draft is intentionally distinguished from a current shared-timeline draft."
            ),
            wraplength=1180,
        )
        intro.pack(anchor="w", pady=(0, 10))
        self.arrangement_tree = ttk.Treeview(
            self.arrangements_tab,
            columns=("configured", "track", "mapping", "draft", "validation", "issues", "xml"),
            show="headings",
        )
        specs = (
            ("configured", "Configured", 95),
            ("track", "Score track", 100),
            ("mapping", "Mapping", 130),
            ("draft", "Draft", 120),
            ("validation", "Validation", 130),
            ("issues", "Flags", 90),
            ("xml", "XML", 100),
        )
        for key, title, width in specs:
            self.arrangement_tree.heading(key, text=title)
            self.arrangement_tree.column(key, width=width, anchor="w")
        self.arrangement_tree.pack(fill="both", expand=True)

    def _build_review_queue(self) -> None:
        controls = ttk.Frame(self.review_tab)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(
            controls,
            text="Validation findings from Bass, Lead, and Rhythm are combined into one time-aware review queue.",
        ).pack(side="left")
        ttk.Button(controls, text="Locate on Timeline", command=self._locate_selected_review).pack(side="right")

        panes = ttk.Panedwindow(self.review_tab, orient="vertical")
        panes.pack(fill="both", expand=True)
        top = ttk.Frame(panes)
        bottom = ttk.LabelFrame(panes, text="Selected review item", padding=10)
        panes.add(top, weight=4)
        panes.add(bottom, weight=1)

        self.review_tree = ttk.Treeview(
            top,
            columns=("severity", "arrangement", "time", "stage", "message"),
            show="headings",
            selectmode="browse",
        )
        specs = (
            ("severity", "Severity", 90),
            ("arrangement", "Arrangement", 100),
            ("time", "Time", 90),
            ("stage", "Stage", 140),
            ("message", "Message", 760),
        )
        for key, title, width in specs:
            self.review_tree.heading(key, text=title)
            self.review_tree.column(key, width=width, anchor="w")
        self.review_tree.pack(fill="both", expand=True)
        self.review_tree.bind("<<TreeviewSelect>>", self._review_selected)
        self.review_tree.bind("<Double-1>", lambda _event: self._locate_selected_review())
        ttk.Label(bottom, textvariable=self.review_detail_var, wraplength=1180).pack(anchor="w")

    def _build_sources(self) -> None:
        ttk.Label(
            self.sources_tab,
            textvariable=self.source_summary_var,
            wraplength=1180,
            justify="left",
        ).pack(anchor="w")
        ttk.Separator(self.sources_tab).pack(fill="x", pady=12)
        ttk.Label(
            self.sources_tab,
            text=(
                "This view is read-only. Source-rights decisions and score-track confirmation remain explicit human actions in the main desktop window. "
                "The Song Workspace never promotes provenance or mapping authority merely by displaying it."
            ),
            wraplength=1180,
        ).pack(anchor="w")

    def refresh(self) -> None:
        try:
            snapshot = build_song_workspace_snapshot(self.project)
        except Exception as exc:
            self.health_var.set(f"Could not refresh: {exc}")
            return
        self.snapshot = snapshot
        self.song_var.set(snapshot.project_name)
        self.health_var.set(f"Project health: {snapshot.health}")
        self.progress_var.set(snapshot.progress_percent)
        self.progress_text_var.set(
            f"{snapshot.complete_steps}/{snapshot.total_steps} workflow steps complete · {snapshot.progress_percent}%"
        )
        if snapshot.next_action_title:
            self.next_action_var.set(f"{snapshot.next_action_title}: {snapshot.next_action_reason or ''}")
        else:
            self.next_action_var.set("No remaining blocking or ready workflow step.")

        recording_review = "reviewed" if snapshot.sources.recording_reviewed else "rights review needed"
        self.overview_vars["recording"].set(
            f"{snapshot.duration_seconds:.1f}s · {recording_review}\nSHA-256 {snapshot.sources.recording_sha256[:12]}…"
        )
        if snapshot.sources.score_filename:
            score_review = "reviewed" if snapshot.sources.score_reviewed else "rights review needed"
            self.overview_vars["score"].set(
                f"{snapshot.sources.score_filename}\n{snapshot.sources.score_format or ''} · {snapshot.sources.score_track_count} tracks · {score_review}"
            )
        else:
            self.overview_vars["score"].set("No complete score registered")

        timeline = snapshot.timeline
        if timeline.shared_timeline_current:
            confidence = f"{timeline.shared_timeline_confidence:.2f}" if timeline.shared_timeline_confidence is not None else "—"
            self.overview_vars["timeline"].set(
                f"Current · confidence {confidence}\n{len(timeline.shared_anchor_audio_times)} reviewed anchors"
            )
        elif timeline.shared_timeline_problem:
            self.overview_vars["timeline"].set("Present but stale/invalid\nReview required before inheritance")
        else:
            self.overview_vars["timeline"].set("Not promoted yet")
        fails = sum(item.severity == "FAIL" for item in snapshot.review_queue)
        warnings = sum(item.severity == "WARNING" for item in snapshot.review_queue)
        self.overview_vars["review"].set(
            f"{len(snapshot.review_queue)} queued items\n{fails} failures · {warnings} warnings"
        )

        self._refresh_arrangements(snapshot)
        self._refresh_review_queue(snapshot)
        self._refresh_sources(snapshot)
        self._refresh_timeline_summary(snapshot)
        self._draw_timeline()

    def _refresh_arrangements(self, snapshot: SongWorkspaceSnapshot) -> None:
        for tree in (self.overview_tree, self.arrangement_tree):
            tree.delete(*tree.get_children())
        for arrangement in snapshot.arrangements:
            mapping = (
                f"track {arrangement.score_track_index}"
                if arrangement.score_track_index is not None
                else "not selected"
            )
            mapping_state = "confirmed" if arrangement.mapping_confirmed else "review needed"
            validation = arrangement.validation_state
            if arrangement.validation_state != "NOT_RUN":
                validation += f" ({arrangement.fail_count}F/{arrangement.warning_count}W)"
            values_overview = (
                arrangement.role.title(),
                f"{mapping} · {mapping_state}",
                arrangement.draft_state,
                validation,
                "ready" if arrangement.export_xml_ready else "not exported",
            )
            self.overview_tree.insert("", "end", values=values_overview)
            self.arrangement_tree.insert(
                "",
                "end",
                text=arrangement.role,
                values=(
                    "yes" if arrangement.configured else "no",
                    arrangement.score_track_index if arrangement.score_track_index is not None else "—",
                    mapping_state,
                    arrangement.draft_state,
                    arrangement.validation_state,
                    arrangement.fail_count + arrangement.warning_count,
                    "ready" if arrangement.export_xml_ready else "—",
                ),
            )

    def _refresh_review_queue(self, snapshot: SongWorkspaceSnapshot) -> None:
        self.review_tree.delete(*self.review_tree.get_children())
        for index, item in enumerate(snapshot.review_queue):
            time_text = f"{item.time_seconds:.3f}s" if item.time_seconds is not None else "—"
            self.review_tree.insert(
                "",
                "end",
                iid=f"review-{index}",
                values=(item.severity, item.arrangement.title(), time_text, item.stage, item.message),
            )
        # Rebuilding the tree above always drops any prior row selection, so the
        # detail label below it must be reset on every refresh rather than only
        # when the queue is empty. Otherwise a stale "no findings queued" message
        # (set on an earlier, empty-queue refresh) keeps showing next to newly
        # populated FAIL/WARNING rows until a row happens to be clicked.
        if not snapshot.review_queue:
            self.review_detail_var.set("No persisted validation findings are currently queued.")
        else:
            fails = sum(item.severity == "FAIL" for item in snapshot.review_queue)
            warnings = sum(item.severity == "WARNING" for item in snapshot.review_queue)
            self.review_detail_var.set(
                f"{len(snapshot.review_queue)} items queued ({fails} failures · {warnings} warnings). "
                "Select a row to see details."
            )

    def _refresh_sources(self, snapshot: SongWorkspaceSnapshot) -> None:
        source = snapshot.sources
        lines = [
            f"Recording\n  SHA-256: {source.recording_sha256}\n  Rights/provenance: {'reviewed' if source.recording_reviewed else 'review required'}",
        ]
        if source.score_filename and source.score_sha256:
            lines.append(
                "Complete score\n"
                f"  File: {source.score_filename}\n"
                f"  Format: {source.score_format}\n"
                f"  Tracks: {source.score_track_count}\n"
                f"  SHA-256: {source.score_sha256}\n"
                f"  Rights/provenance: {'reviewed' if source.score_reviewed else 'review required'}"
            )
        else:
            lines.append("Complete score\n  Not registered")
        self.source_summary_var.set("\n\n".join(lines))

    def _refresh_timeline_summary(self, snapshot: SongWorkspaceSnapshot) -> None:
        timeline = snapshot.timeline
        parts = [f"Duration {timeline.duration_seconds:.2f}s", f"{len(timeline.beat_times)} detected beats"]
        if timeline.low_confidence_beats:
            parts.append(f"{timeline.low_confidence_beats} low-confidence beats")
        if timeline.shared_timeline_current:
            parts.append(f"{len(timeline.shared_anchor_audio_times)} shared anchors")
        elif timeline.shared_timeline_problem:
            parts.append("shared timeline stale/invalid")
        else:
            parts.append("shared timeline not promoted")
        self.timeline_summary_var.set(" · ".join(parts))

    def _timeline_x(self, time_seconds: float, width: float, duration: float) -> float:
        margin = 45.0
        usable = max(width - (2 * margin), 1.0)
        if duration <= 0:
            return margin
        bounded = min(max(time_seconds, 0.0), duration)
        return margin + (bounded / duration) * usable

    def _draw_timeline(self) -> None:
        canvas = self.timeline_canvas
        canvas.delete("all")
        snapshot = self.snapshot
        if snapshot is None:
            return
        width = max(canvas.winfo_width(), 200)
        height = max(canvas.winfo_height(), 240)
        duration = max(snapshot.duration_seconds, 0.001)
        margin = 45
        top_y = 70
        anchor_y = height / 2
        review_y = height - 75

        canvas.create_line(margin, top_y, width - margin, top_y)
        canvas.create_line(margin, anchor_y, width - margin, anchor_y)
        canvas.create_line(margin, review_y, width - margin, review_y)
        canvas.create_text(8, top_y, text="Beats", anchor="w")
        canvas.create_text(8, anchor_y, text="Anchors", anchor="w")
        canvas.create_text(8, review_y, text="Review", anchor="w")

        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            when = duration * fraction
            x = self._timeline_x(when, width, duration)
            canvas.create_line(x, top_y - 18, x, review_y + 18, dash=(2, 4))
            canvas.create_text(x, review_y + 30, text=self._format_time(when), anchor="n")

        beat_times = snapshot.timeline.beat_times
        stride = max(1, len(beat_times) // max(int(width // 4), 1))
        for index, when in enumerate(beat_times):
            if index % stride:
                continue
            x = self._timeline_x(when, width, duration)
            canvas.create_line(x, top_y - 8, x, top_y + 8)

        for when in snapshot.timeline.shared_anchor_audio_times:
            x = self._timeline_x(when, width, duration)
            canvas.create_oval(x - 3, anchor_y - 3, x + 3, anchor_y + 3, fill="black")

        for item in snapshot.review_queue:
            if item.time_seconds is None:
                continue
            x = self._timeline_x(item.time_seconds, width, duration)
            marker_height = 15 if item.severity == "FAIL" else 10
            canvas.create_line(x, review_y - marker_height, x, review_y + marker_height, width=2)

        if self._selected_time is not None:
            x = self._timeline_x(self._selected_time, width, duration)
            canvas.create_line(x, top_y - 25, x, review_y + 25, width=2)

    def _timeline_clicked(self, event: tk.Event) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        width = max(self.timeline_canvas.winfo_width(), 200)
        margin = 45.0
        usable = max(width - 2 * margin, 1.0)
        fraction = min(max((float(event.x) - margin) / usable, 0.0), 1.0)
        self._selected_time = fraction * snapshot.duration_seconds
        self.timeline_cursor_var.set(f"Cursor: {self._format_time(self._selected_time)} ({self._selected_time:.3f}s)")
        self._draw_timeline()

    def _selected_review_item(self) -> WorkspaceReviewItem | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        selection = self.review_tree.selection()
        if not selection:
            return None
        iid = selection[0]
        try:
            index = int(iid.rsplit("-", 1)[1])
        except (ValueError, IndexError):
            return None
        if index < 0 or index >= len(snapshot.review_queue):
            return None
        return snapshot.review_queue[index]

    def _review_selected(self, _event=None) -> None:
        item = self._selected_review_item()
        if item is None:
            return
        location = f" at {item.time_seconds:.3f}s" if item.time_seconds is not None else ""
        note = f" · note {item.note_index}" if item.note_index is not None else ""
        self.review_detail_var.set(
            f"{item.severity} · {item.arrangement.title()} · {item.stage}/{item.code}{location}{note}\n{item.message}"
        )

    def _locate_selected_review(self) -> None:
        item = self._selected_review_item()
        if item is None or item.time_seconds is None:
            return
        self._selected_time = item.time_seconds
        self.timeline_cursor_var.set(f"Cursor: {self._format_time(item.time_seconds)} ({item.time_seconds:.3f}s)")
        self.notebook.select(self.timeline_tab)
        self._draw_timeline()

    def open_project_folder(self) -> None:
        if os.name == "nt":
            os.startfile(self.project)  # type: ignore[attr-defined]

    @staticmethod
    def _format_time(seconds: float) -> str:
        minutes = int(seconds // 60)
        remaining = seconds - (minutes * 60)
        return f"{minutes}:{remaining:05.2f}"
