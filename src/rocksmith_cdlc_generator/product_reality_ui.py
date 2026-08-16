from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .product_reality import (
    CorrectionCategory,
    ProductRealitySession,
    add_product_reality_observation,
    finish_product_reality_session,
    increment_product_reality_correction,
    load_active_product_reality_session,
    product_reality_live_metrics,
    start_product_reality_session,
    start_product_reality_stage,
    stop_product_reality_stage,
)

_STAGE_CHOICES = (
    "launch / open project",
    "recording + score intake",
    "Bass / Lead / Rhythm mapping",
    "shared timing review",
    "arrangement review / correction",
    "validation / export",
    "DLC Builder / package verification",
    "other",
)
_CORRECTION_CATEGORIES: tuple[CorrectionCategory, ...] = (
    "timing",
    "position",
    "technique",
    "chord_fingering",
    "chord_identity",
    "other",
)


class ProductRealityRecorderWindow(tk.Toplevel):
    """Separate evidence recorder for real packaged-app Product Reality sessions."""

    def __init__(self, parent: tk.Misc, project: Path) -> None:
        super().__init__(parent)
        self.project = project.expanduser().resolve()
        self._live_refresh_after_id: str | None = None
        self.title("Product Reality Gate Recorder")
        self.geometry("920x720")
        self.minsize(820, 620)
        self._build()
        self.refresh()

    def set_project(self, project: Path) -> None:
        self.project = project.expanduser().resolve()
        self.refresh()

    def destroy(self) -> None:
        if self._live_refresh_after_id is not None:
            try:
                self.after_cancel(self._live_refresh_after_id)
            except tk.TclError:
                pass
            self._live_refresh_after_id = None
        super().destroy()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        intro = ttk.Label(
            root,
            text=(
                "Record real packaged-app workflow evidence. This window measures usability and correction work; "
                "it creates no musical, mapping, timing, validation, tone, or package authority."
            ),
            wraplength=870,
            justify="left",
        )
        intro.pack(fill="x")

        session_box = ttk.LabelFrame(root, text="Session", padding=8)
        session_box.pack(fill="x", pady=(10, 0))
        session_row = ttk.Frame(session_box)
        session_row.pack(fill="x")
        ttk.Label(session_row, text="Packaged build / artifact ID").pack(side="left")
        self.build_id_var = tk.StringVar(value="")
        ttk.Entry(session_row, textvariable=self.build_id_var, width=34).pack(side="left", padx=(6, 10))
        self.start_session_button = ttk.Button(
            session_row, text="Start Reality Session", command=self._start_session
        )
        self.start_session_button.pack(side="left")
        self.session_status_var = tk.StringVar(value="No Product Reality session is active.")
        ttk.Label(
            session_box,
            textvariable=self.session_status_var,
            wraplength=870,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        stage_box = ttk.LabelFrame(root, text="Workflow stage timer", padding=8)
        stage_box.pack(fill="x", pady=(10, 0))
        stage_row = ttk.Frame(stage_box)
        stage_row.pack(fill="x")
        self.stage_var = tk.StringVar(value=_STAGE_CHOICES[0])
        ttk.Combobox(
            stage_row,
            textvariable=self.stage_var,
            values=_STAGE_CHOICES,
            state="readonly",
            width=36,
        ).pack(side="left")
        self.stage_counts_as_editing_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            stage_row,
            text="Count toward editing time",
            variable=self.stage_counts_as_editing_var,
        ).pack(side="left", padx=(10, 12))
        self.start_stage_button = ttk.Button(stage_row, text="Start Stage", command=self._start_stage)
        self.start_stage_button.pack(side="left")
        self.stop_stage_button = ttk.Button(stage_row, text="Stop Stage", command=self._stop_stage)
        self.stop_stage_button.pack(side="left", padx=(6, 0))

        correction_box = ttk.LabelFrame(root, text="Correction counter", padding=8)
        correction_box.pack(fill="x", pady=(10, 0))
        correction_row = ttk.Frame(correction_box)
        correction_row.pack(fill="x")
        self.correction_arrangement_var = tk.StringVar(value="bass")
        ttk.Combobox(
            correction_row,
            textvariable=self.correction_arrangement_var,
            values=("bass", "lead", "rhythm"),
            state="readonly",
            width=12,
        ).pack(side="left")
        self.correction_category_var = tk.StringVar(value="timing")
        ttk.Combobox(
            correction_row,
            textvariable=self.correction_category_var,
            values=_CORRECTION_CATEGORIES,
            state="readonly",
            width=20,
        ).pack(side="left", padx=(6, 10))
        self.add_correction_button = ttk.Button(
            correction_row,
            text="+1 Correction",
            command=self._add_correction,
        )
        self.add_correction_button.pack(side="left")
        self.correction_status_var = tk.StringVar(value="No corrections recorded.")
        ttk.Label(correction_box, textvariable=self.correction_status_var).pack(anchor="w", pady=(6, 0))

        observation_box = ttk.LabelFrame(root, text="Observation / workaround", padding=8)
        observation_box.pack(fill="x", pady=(10, 0))
        observation_top = ttk.Frame(observation_box)
        observation_top.pack(fill="x")
        ttk.Label(observation_top, text="Area").pack(side="left")
        self.observation_area_var = tk.StringVar(value="arrangement editing")
        ttk.Entry(observation_top, textvariable=self.observation_area_var, width=28).pack(
            side="left", padx=(6, 10)
        )
        self.observation_severity_var = tk.StringVar(value="friction")
        ttk.Combobox(
            observation_top,
            textvariable=self.observation_severity_var,
            values=("note", "friction", "blocker"),
            state="readonly",
            width=12,
        ).pack(side="left")
        self.observation_cli_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            observation_top,
            text="Required CLI / PowerShell",
            variable=self.observation_cli_var,
        ).pack(side="left", padx=(10, 0))
        self.observation_text = tk.Text(observation_box, height=4, wrap="word")
        self.observation_text.pack(fill="x", pady=(6, 6))
        self.add_observation_button = ttk.Button(
            observation_box,
            text="Record Observation",
            command=self._add_observation,
        )
        self.add_observation_button.pack(anchor="e")

        decision_box = ttk.LabelFrame(root, text="Gate decision", padding=8)
        decision_box.pack(fill="x", pady=(10, 0))
        ttk.Label(
            decision_box,
            text="Finish only after the real session. Record why the current Product Reality Gate passed or failed.",
            wraplength=870,
            justify="left",
        ).pack(anchor="w")
        self.gate_reason_text = tk.Text(decision_box, height=4, wrap="word")
        self.gate_reason_text.pack(fill="x", pady=(6, 6))
        decision_row = ttk.Frame(decision_box)
        decision_row.pack(fill="x")
        self.finish_pass_button = ttk.Button(
            decision_row, text="Finish: PASS", command=lambda: self._finish("pass")
        )
        self.finish_pass_button.pack(side="right")
        self.finish_fail_button = ttk.Button(
            decision_row, text="Finish: FAIL", command=lambda: self._finish("fail")
        )
        self.finish_fail_button.pack(side="right", padx=(0, 6))

        self.summary_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.summary_var, wraplength=870, justify="left").pack(
            fill="x", pady=(10, 0)
        )

    def _active(self) -> ProductRealitySession | None:
        return load_active_product_reality_session(self.project)

    def _schedule_live_refresh(self, enabled: bool) -> None:
        if self._live_refresh_after_id is not None:
            self.after_cancel(self._live_refresh_after_id)
            self._live_refresh_after_id = None
        if enabled:
            self._live_refresh_after_id = self.after(1000, self._live_refresh)

    def _live_refresh(self) -> None:
        self._live_refresh_after_id = None
        try:
            self.refresh()
        except tk.TclError:
            return

    def refresh(self) -> None:
        try:
            session = self._active()
        except (OSError, ValueError) as exc:
            self._schedule_live_refresh(False)
            self._set_controls(False)
            self.session_status_var.set(f"Product Reality recorder unavailable: {exc}")
            return

        active = session is not None
        self.start_session_button.configure(state="disabled" if active else "normal")
        self.build_id_var.set("" if session is None else (session.packaged_build_id or ""))
        self._set_controls(active)
        if session is None:
            self._schedule_live_refresh(False)
            self.session_status_var.set("No Product Reality session is active for this project.")
            self.correction_status_var.set("No corrections recorded.")
            self.summary_var.set("")
            return

        try:
            live = product_reality_live_metrics(session)
        except ValueError as exc:
            self._schedule_live_refresh(False)
            self.session_status_var.set(f"Product Reality recorder unavailable: {exc}")
            return

        if session.active_stage_name is None:
            self.start_stage_button.configure(state="normal")
            self.stop_stage_button.configure(state="disabled")
            stage_text = "no stage timer running"
        else:
            self.start_stage_button.configure(state="disabled")
            self.stop_stage_button.configure(state="normal")
            stage_text = (
                f"stage running: {session.active_stage_name} "
                f"({live.active_stage_elapsed_seconds / 60.0:.2f} min)"
            )
        self._schedule_live_refresh(session.active_stage_name is not None)
        self.session_status_var.set(
            f"Session {session.session_id[:8]} · {stage_text} · score: "
            f"{session.score_format or 'none registered'}"
        )
        self.correction_status_var.set(
            f"{session.total_corrections} correction(s) recorded across Bass/Lead/Rhythm."
        )
        self.summary_var.set(
            f"Live measured work {live.measured_work_seconds / 60.0:.2f} min · "
            f"live editing {live.editing_seconds / 60.0:.2f} min · "
            f"live editing minutes / finished minute {live.editing_minutes_per_finished_minute:.3f} · "
            f"observations {len(session.observations)} · CLI/PowerShell workarounds {session.cli_workaround_count}"
        )

    def _set_controls(self, active: bool) -> None:
        state = "normal" if active else "disabled"
        for control in (
            self.start_stage_button,
            self.stop_stage_button,
            self.add_correction_button,
            self.add_observation_button,
            self.finish_pass_button,
            self.finish_fail_button,
        ):
            control.configure(state=state)

    def _start_session(self) -> None:
        try:
            start_product_reality_session(
                self.project,
                packaged_build_id=self.build_id_var.get(),
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Product Reality Gate", str(exc), parent=self)
            return
        self.refresh()

    def _start_stage(self) -> None:
        try:
            start_product_reality_stage(
                self.project,
                name=self.stage_var.get(),
                counts_as_editing=self.stage_counts_as_editing_var.get(),
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Product Reality Gate", str(exc), parent=self)
            return
        self.refresh()

    def _stop_stage(self) -> None:
        try:
            stop_product_reality_stage(self.project)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Product Reality Gate", str(exc), parent=self)
            return
        self.refresh()

    def _add_correction(self) -> None:
        try:
            increment_product_reality_correction(
                self.project,
                arrangement=self.correction_arrangement_var.get(),  # type: ignore[arg-type]
                category=self.correction_category_var.get(),  # type: ignore[arg-type]
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Product Reality Gate", str(exc), parent=self)
            return
        self.refresh()

    def _add_observation(self) -> None:
        try:
            add_product_reality_observation(
                self.project,
                area=self.observation_area_var.get(),
                severity=self.observation_severity_var.get(),  # type: ignore[arg-type]
                text=self.observation_text.get("1.0", "end").strip(),
                requires_cli_or_powershell=self.observation_cli_var.get(),
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Product Reality Gate", str(exc), parent=self)
            return
        self.observation_text.delete("1.0", "end")
        self.observation_cli_var.set(False)
        self.refresh()

    def _finish(self, result: str) -> None:
        try:
            completed, json_path, markdown_path = finish_product_reality_session(
                self.project,
                result=result,  # type: ignore[arg-type]
                reason=self.gate_reason_text.get("1.0", "end").strip(),
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Product Reality Gate", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Product Reality Gate",
            (
                f"Session finished: {completed.gate_result.upper()}\n\n"
                f"JSON: {json_path.relative_to(self.project)}\n"
                f"Report: {markdown_path.relative_to(self.project)}"
            ),
            parent=self,
        )
        self.gate_reason_text.delete("1.0", "end")
        self.refresh()
