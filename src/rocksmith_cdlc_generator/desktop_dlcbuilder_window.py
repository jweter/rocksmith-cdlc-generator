from __future__ import annotations

import math
from pathlib import Path
from typing import Callable
import tkinter as tk
from tkinter import ttk

PrepareSuccess = Callable[[Path], None]
PrepareFailure = Callable[[Exception], None]
PrepareRequest = Callable[[float, str | None, PrepareSuccess, PrepareFailure], bool]


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
    """Prepare the validation-gated DLC Builder project without touching Rocksmith."""

    def __init__(
        self,
        parent: tk.Misc,
        project: Path,
        *,
        prepare_request: PrepareRequest,
    ) -> None:
        super().__init__(parent)
        self.project = project.expanduser().resolve()
        self._prepare_request = prepare_request
        self.title("DLC Builder Preparation — Rocksmith CDLC Generator")
        self.geometry("900x390")
        self.minsize(760, 340)

        ttk.Label(
            self,
            text=(
                "Prepare a project-local DLC Builder .rs2dlc file from the current validated "
                "Bass, Lead, and Rhythm XML plus confirmed metadata/cover. This does not launch "
                "DLC Builder, build a PSARC, or modify the live Rocksmith installation."
            ),
            wraplength=850,
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
        ttk.Label(actions, textvariable=self.status_var, wraplength=600).pack(
            side="left", fill="x", expand=True, padx=(14, 0)
        )

        ttk.Separator(self).pack(fill="x", padx=12, pady=12)
        ttk.Label(
            self,
            text=(
                "Preparation re-runs the existing arrangement/package readiness gates. Generated preview audio "
                "and .rs2dlc data remain inside the private project build directory and must not be committed."
            ),
            wraplength=850,
            justify="left",
        ).pack(anchor="w", padx=12)

    def set_project(self, project: Path) -> None:
        resolved = project.expanduser().resolve()
        if resolved != self.project:
            self.preview_start_var.set("30.0")
            self.dlc_key_var.set("")
        self.project = resolved
        self.status_var.set("Not prepared in this session")

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
        self.status_var.set("Preparation running…")

    def _succeeded(self, destination: Path) -> None:
        self.status_var.set(f"Prepared: {destination}")

    def _failed(self, error: Exception) -> None:
        self.status_var.set(f"Preparation failed: {error}")
