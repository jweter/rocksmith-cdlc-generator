from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Literal
import tkinter as tk
from tkinter import ttk

from .desktop_shell import ProductDesktopApp
from .multi_arrangement_plan import build_multi_arrangement_workflow_plan
from .project_source_inventory import ProjectSourceInventory, build_project_source_inventory
from .song_readiness import SongReadiness, build_song_readiness


GuidedActionRoute = Literal["automatic", "score", "rights", "song-review", "workflow"]
RightsChoice = tuple[str, bool, str]
_TASK_STATUS_NAME = "automatic_task_status.json"


class GuidedDesktopApp(ProductDesktopApp):
    """Primary product shell that puts user progress ahead of pipeline details."""

    def _build_layout(self) -> None:
        super()._build_layout()
        self.run_button.configure(text="Continue Automatically")

        self.readiness_headline_var = tk.StringVar(value="Open or create a song project to begin")
        self.readiness_detail_var = tk.StringVar(
            value="Choose one recording and, when available, one complete score for Bass, Lead, and Rhythm."
        )
        self.readiness_percent_var = tk.DoubleVar(value=0.0)
        self.readiness_percent_text_var = tk.StringVar(value="0% prepared")
        self.task_status_var = tk.StringVar(value="No automatic task running.")
        self.task_progress_var = tk.DoubleVar(value=0.0)
        self._guided_action_route: GuidedActionRoute | None = None
        self._task_poll_after_id: str | None = None
        self._task_started_at = 0.0
        self._last_task_log_message = ""

        children = self.winfo_children()
        before = children[1] if len(children) > 1 else None
        readiness = ttk.LabelFrame(self, text="Song progress", padding=12)
        pack_options = {"fill": "x", "padx": 12, "pady": (0, 8)}
        if before is not None:
            pack_options["before"] = before
        readiness.pack(**pack_options)

        header = ttk.Frame(readiness)
        header.pack(fill="x")
        ttk.Label(
            header,
            textvariable=self.readiness_headline_var,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")
        ttk.Label(header, textvariable=self.readiness_percent_text_var).pack(side="right")

        self.readiness_progress = ttk.Progressbar(
            readiness,
            maximum=100,
            variable=self.readiness_percent_var,
        )
        self.readiness_progress.pack(fill="x", pady=(8, 8))

        action_row = ttk.Frame(readiness)
        action_row.pack(fill="x")
        ttk.Label(
            action_row,
            textvariable=self.readiness_detail_var,
            wraplength=820,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        self.next_action_button = ttk.Button(
            action_row,
            text="Next Step",
            command=self._run_guided_action,
            state="disabled",
        )
        self.next_action_button.pack(side="right", padx=(12, 0))

        task_row = ttk.Frame(readiness)
        task_row.pack(fill="x", pady=(10, 0))
        ttk.Label(
            task_row,
            textvariable=self.task_status_var,
            wraplength=980,
            justify="left",
        ).pack(fill="x")
        self.task_progress = ttk.Progressbar(
            task_row,
            maximum=100,
            variable=self.task_progress_var,
        )
        self.task_progress.pack(fill="x", pady=(4, 0))

    @staticmethod
    def readiness_display(readiness: SongReadiness) -> tuple[str, str]:
        headline = f"{readiness.percent}% prepared — {readiness.headline}"
        if readiness.next_action is None:
            detail = "No remaining authoring workflow action is currently required."
        elif readiness.next_action.kind == "needs_you":
            detail = f"Needs you next: {readiness.next_action.title}. {readiness.next_action.detail}"
        elif readiness.next_action.kind == "automatic":
            detail = f"Ready next: {readiness.next_action.title}. Use Continue Automatically."
        else:
            detail = f"Next: {readiness.next_action.title}. {readiness.next_action.detail}"
        return headline, detail

    @staticmethod
    def guided_action_spec(readiness: SongReadiness) -> tuple[str, GuidedActionRoute] | None:
        """Return the safest direct UI destination for the current actionable step."""

        action = readiness.next_action
        if action is None:
            return None
        if action.kind == "automatic":
            return ("Continue Automatically", "automatic")

        routes: dict[str, tuple[str, GuidedActionRoute]] = {
            "source-rights": ("Review Source Rights", "rights"),
            "score-arrangements": ("Review Score Tracks", "score"),
            "align-tab": ("Open Song Review", "song-review"),
            "shared-timeline": ("Open Song Review", "song-review"),
            "human-review": ("Open Song Review", "song-review"),
        }
        if action.step_id in routes:
            return routes[action.step_id]
        if action.kind == "needs_you":
            return ("Show Workflow Details", "workflow")
        return None

    @staticmethod
    def source_rights_choices_from_inventory(
        inventory: ProjectSourceInventory,
    ) -> dict[str, RightsChoice]:
        """Collapse duplicate receipts by content without hiding unresolved conflicts."""

        by_sha: dict[str, list] = {}
        for item in inventory.local_sources:
            by_sha.setdefault(item.source_sha256, []).append(item)

        choices: dict[str, RightsChoice] = {}
        for sha, items in by_sha.items():
            first = items[0]
            rights_classes = {item.rights_class for item in items}
            required = any(item.human_rights_review_required for item in items) or len(rights_classes) != 1
            rights_class = "unknown" if required else next(iter(rights_classes))
            label = f"{first.display_name} — {first.source_format} — {sha[:12]}…"
            choices[label] = (sha, required, rights_class)
        return choices

    @staticmethod
    def source_choices_from_inventory(inventory: ProjectSourceInventory) -> dict[str, str]:
        """Compatibility view for callers that only need label-to-hash choices."""

        return {
            label: sha
            for label, (sha, _required, _rights_class) in GuidedDesktopApp.source_rights_choices_from_inventory(
                inventory
            ).items()
        }

    @staticmethod
    def first_unreviewed_source_label(
        choices: dict[str, RightsChoice] | dict[str, str],
        reviews: dict[str, object] | None = None,
    ) -> str | None:
        """Return the first source that still requires rights review."""

        for label, value in choices.items():
            if isinstance(value, tuple):
                if value[1]:
                    return label
            elif reviews is not None and value not in reviews:
                return label
        return None

    def _inventory_rights_choices(self) -> dict[str, RightsChoice]:
        if self.project is None:
            return {}
        inventory = build_project_source_inventory(self.project)
        return self.source_rights_choices_from_inventory(inventory)

    def _source_choices(self) -> dict[str, str]:
        return {
            label: sha
            for label, (sha, _required, _rights_class) in self._inventory_rights_choices().items()
        }

    def _refresh_rights(self) -> None:
        try:
            choices = self._inventory_rights_choices()
        except Exception as exc:
            self._set_rights_text(f"Could not load rights state: {exc}")
            return
        labels = list(choices)
        self.rights_source_combo.configure(values=labels)
        if labels and self.rights_source_var.get() not in choices:
            self.rights_source_var.set(labels[0])
        lines = []
        for label, (_sha, required, rights_class) in choices.items():
            if required:
                lines.append(f"REVIEW NEEDED  {label}")
            else:
                lines.append(f"REVIEWED       {label}  →  {rights_class}")
        self._set_rights_text("\n".join(lines) if lines else "No local project sources found.")

    def _select_primary_tab(self, tab: ttk.Frame) -> None:
        notebook = tab.master
        if isinstance(notebook, ttk.Notebook):
            notebook.select(tab)

    def _focus_unreviewed_rights_source(self) -> None:
        try:
            choices = self._inventory_rights_choices()
        except Exception:
            choices = {}
        label = self.first_unreviewed_source_label(choices)
        if label is not None:
            self.rights_source_var.set(label)
        self.rights_source_combo.focus_set()

    def _run_guided_action(self) -> None:
        route = self._guided_action_route
        if route == "automatic":
            self.run_automatic_steps()
        elif route == "score":
            self._select_primary_tab(self.score_tab)
            self.mapping_combos[next(iter(self.mapping_combos))].focus_set()
        elif route == "rights":
            self._select_primary_tab(self.rights_tab)
            self._focus_unreviewed_rights_source()
        elif route == "song-review":
            self.open_song_workspace()
        elif route == "workflow":
            self._select_primary_tab(self.workflow_tab)

    def _update_guided_action(self, readiness: SongReadiness) -> None:
        spec = self.guided_action_spec(readiness)
        if spec is None:
            self._guided_action_route = None
            self.next_action_button.configure(text="Next Step", state="disabled")
            return
        label, route = spec
        self._guided_action_route = route
        self.next_action_button.configure(text=label, state="normal")

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        super()._set_busy(busy, message)
        if not hasattr(self, "task_status_var"):
            return
        if self._task_poll_after_id is not None:
            try:
                self.after_cancel(self._task_poll_after_id)
            except tk.TclError:
                pass
            self._task_poll_after_id = None
        if busy:
            self._task_started_at = time.time()
            self._last_task_log_message = ""
            self.task_progress_var.set(0.0)
            self.task_status_var.set(f"Current task: {message or 'Working…'} — starting")
            self._poll_task_progress()
        else:
            self.task_status_var.set(message or "Automatic task finished.")

    def _poll_task_progress(self) -> None:
        if not self._busy:
            self._task_poll_after_id = None
            return
        project = self.project
        if project is not None:
            status_path = Path(project) / "review" / _TASK_STATUS_NAME
            try:
                payload = json.loads(status_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                payload = None
            if isinstance(payload, dict):
                updated_at = payload.get("updated_at")
                if isinstance(updated_at, (int, float)) and updated_at >= self._task_started_at - 1.0:
                    percent = payload.get("percent", 0.0)
                    try:
                        percent_value = max(0.0, min(100.0, float(percent)))
                    except (TypeError, ValueError):
                        percent_value = 0.0
                    message = str(payload.get("message") or "Working")
                    task = str(payload.get("task") or "Automatic task")
                    started_at = payload.get("started_at")
                    elapsed = time.time() - float(started_at) if isinstance(started_at, (int, float)) else 0.0
                    heartbeat_age = max(0.0, time.time() - float(updated_at))
                    self.task_progress_var.set(percent_value)
                    self.task_status_var.set(
                        f"Current task: {task} — {message} — {percent_value:.0f}% — "
                        f"elapsed {elapsed:.0f}s — last update {heartbeat_age:.0f}s ago"
                    )
                    log_key = f"{message}|{percent_value:.1f}"
                    if log_key != self._last_task_log_message:
                        self._last_task_log_message = log_key
                        self._log(f"Task progress: {message} ({percent_value:.0f}%)")
        self._task_poll_after_id = self.after(500, self._poll_task_progress)

    def refresh_project(self) -> None:
        super().refresh_project()
        project = self.project
        if project is None or not (Path(project) / "project.json").is_file():
            self._guided_action_route = None
            if hasattr(self, "next_action_button"):
                self.next_action_button.configure(text="Next Step", state="disabled")
            return
        try:
            readiness = build_song_readiness(build_multi_arrangement_workflow_plan(project))
        except Exception:
            self._guided_action_route = None
            self.next_action_button.configure(text="Next Step", state="disabled")
            return
        headline, detail = self.readiness_display(readiness)
        self.readiness_headline_var.set(headline)
        self.readiness_detail_var.set(detail)
        self.readiness_percent_var.set(float(readiness.percent))
        self.readiness_percent_text_var.set(f"{readiness.percent}% prepared")
        self._update_guided_action(readiness)


def main() -> None:
    app = GuidedDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
