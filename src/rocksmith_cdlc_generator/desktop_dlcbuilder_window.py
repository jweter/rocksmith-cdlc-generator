from __future__ import annotations

import math
from pathlib import Path
from typing import Callable
import tkinter as tk
from tkinter import filedialog, ttk

from .desktop_dlcbuilder_tools import (
    discover_dlcbuilder_executable,
    require_dlcbuilder_executable,
)

PrepareSuccess = Callable[[Path], None]
PrepareFailure = Callable[[Exception], None]
PrepareRequest = Callable[[float, str | None, PrepareSuccess, PrepareFailure], bool]
LaunchSuccess = Callable[[Path], None]
LaunchFailure = Callable[[Exception], None]
LaunchRequest = Callable[[Path, Path | None, LaunchSuccess, LaunchFailure], bool]


def parse_preview_start(value: str) -> float:
    text = value.strip()
    if not text:
        raise ValueError("Preview start is required")
    try:
        seconds = float(text)
    except ValueError as exc:
        raise ValueError("Preview start must be a number of seconds") from exc
    if not math.isfinite(seconds):
        raise ValueError("Preview start must be a finite number of seconds")
    if seconds < 0:
        raise ValueError("Preview start must be non-negative")
    return seconds


class DlcBuilderPreparationWindow(tk.Toplevel):
    """Prepare and explicitly launch the validation-gated DLC Builder handoff."""

    def __init__(
        self,
        parent: tk.Misc,
        project: Path,
        *,
        prepare_request: PrepareRequest,
        launch_request: LaunchRequest,
    ) -> None:
        super().__init__(parent)
        self.project = project.expanduser().resolve()
        self._prepare_request = prepare_request
        self._launch_request = launch_request
        self._prepared_project: Path | None = None
        self.title("DLC Builder Handoff — Rocksmith CDLC Generator")
        self.geometry("940x510")
        self.minsize(800, 440)

        ttk.Label(
            self,
            text=(
                "Prepare a project-local DLC Builder .rs2dlc file from the current validated "
                "Bass, Lead, and Rhythm XML plus confirmed metadata/cover, then explicitly launch "
                "DLC Builder when you are ready to review and build the package."
            ),
            wraplength=890,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(12, 10))

        form = ttk.LabelFrame(self, text="DLC Builder project preparation", padding=10)
        form.pack(fill="x", padx=12)
        form.columnconfigure(1, weight=1)

        self.preview_start_var = tk.StringVar(value="30.0")
        self.dlc_key_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Not prepared in this session")

        ttk.Label(form, text="Preview start (seconds)", width=22).grid(
            row=0, column=0, sticky="w", pady=5
        )
        ttk.Entry(form, textvariable=self.preview_start_var, width=18).grid(
            row=0, column=1, sticky="w", padx=(8, 0), pady=5
        )
        ttk.Label(form, text="DLC key (optional)", width=22).grid(
            row=1, column=0, sticky="w", pady=5
        )
        ttk.Entry(form, textvariable=self.dlc_key_var).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=5
        )

        actions = ttk.Frame(self, padding=(12, 10, 12, 0))
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="Prepare DLC Builder Project",
            command=self._request,
        ).pack(side="left")
        ttk.Label(actions, textvariable=self.status_var, wraplength=620).pack(
            side="left", fill="x", expand=True, padx=(14, 0)
        )

        launch = ttk.LabelFrame(self, text="DLC Builder executable and launch", padding=10)
        launch.pack(fill="x", padx=12, pady=(14, 0))
        launch.columnconfigure(1, weight=1)

        discovered = discover_dlcbuilder_executable()
        self.executable_var = tk.StringVar(value=str(discovered) if discovered else "")
        self.launch_status_var = tk.StringVar(
            value="DLC Builder detected" if discovered else "DLC Builder executable not detected"
        )

        ttk.Label(launch, text="Executable", width=22).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(launch, textvariable=self.executable_var).grid(
            row=0, column=1, sticky="ew", padx=(8, 6), pady=5
        )
        ttk.Button(launch, text="Browse…", command=self._browse_executable).grid(
            row=0, column=2, padx=4, pady=5
        )
        ttk.Button(launch, text="Detect", command=self._detect_executable).grid(
            row=0, column=3, padx=(4, 0), pady=5
        )
        ttk.Button(launch, text="Launch DLC Builder", command=self._launch).grid(
            row=1, column=0, sticky="w", pady=(8, 4)
        )
        ttk.Label(launch, textvariable=self.launch_status_var, wraplength=650).grid(
            row=1, column=1, columnspan=3, sticky="w", padx=(8, 0), pady=(8, 4)
        )

        ttk.Separator(self).pack(fill="x", padx=12, pady=12)
        ttk.Label(
            self,
            text=(
                "Launch re-runs build staging/readiness checks before starting the external tool. "
                "DLC Builder remains responsible for package construction. This application never "
                "writes to the live Rocksmith installation or NoCableLauncher."
            ),
            wraplength=890,
            justify="left",
        ).pack(anchor="w", padx=12)

    def set_project(self, project: Path) -> None:
        resolved = project.expanduser().resolve()
        if resolved != self.project:
            self.preview_start_var.set("30.0")
            self.dlc_key_var.set("")
            self._prepared_project = None
        self.project = resolved
        self.status_var.set("Not prepared in this session")
        self.launch_status_var.set("Not launched for this project in this session")

    def _request(self) -> None:
        try:
            preview_start = parse_preview_start(self.preview_start_var.get())
        except ValueError as exc:
            self.status_var.set(f"Preparation not started: {exc}")
            return

        dlc_key = self.dlc_key_var.get().strip() or None
        accepted = self._prepare_request(
            preview_start,
            dlc_key,
            self._succeeded,
            self._failed,
        )
        if not accepted:
            self.status_var.set("Preparation not started: another background operation is active.")
            return
        self._prepared_project = None
        self.status_var.set("Preparation running…")

    def _succeeded(self, destination: Path) -> None:
        self._prepared_project = destination.expanduser().resolve()
        self.status_var.set(f"Prepared: {destination}")

    def _failed(self, error: Exception) -> None:
        self.status_var.set(f"Preparation failed: {error}")

    def _browse_executable(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Choose DLC Builder executable",
            filetypes=(("Windows executable", "*.exe"), ("All files", "*.*")),
        )
        if selected:
            self.executable_var.set(selected)
            self.launch_status_var.set("DLC Builder executable selected; launch is still explicit.")

    def _detect_executable(self) -> None:
        discovered = discover_dlcbuilder_executable()
        if discovered is None:
            self.launch_status_var.set(
                "DLC Builder was not found via ROCKSMITH_DLCBUILDER_EXE or PATH. Use Browse…"
            )
            return
        self.executable_var.set(str(discovered))
        self.launch_status_var.set(f"Detected: {discovered}")

    def _launch(self) -> None:
        try:
            executable = require_dlcbuilder_executable(self.executable_var.get())
        except (FileNotFoundError, ValueError) as exc:
            self.launch_status_var.set(f"Launch not started: {exc}")
            return
        accepted = self._launch_request(
            executable,
            self._prepared_project,
            self._launch_succeeded,
            self._launch_failed,
        )
        if not accepted:
            self.launch_status_var.set("Launch not started: another background operation is active.")
            return
        self.launch_status_var.set("Staging current inputs and launching DLC Builder…")

    def _launch_succeeded(self, readiness_path: Path) -> None:
        self.launch_status_var.set(f"DLC Builder launched; readiness: {readiness_path}")

    def _launch_failed(self, error: Exception) -> None:
        self.launch_status_var.set(f"Launch failed: {error}")
