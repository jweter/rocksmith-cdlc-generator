from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .tone_regions import (
    ArrangementToneRegions,
    ToneRegion,
    confirm_tone_regions,
    load_tone_regions,
)

_ARRANGEMENTS = ("bass", "lead", "rhythm")


class ToneRegionsPanel(ttk.Frame):
    """Human-confirmed package tone labels and timed tone-change regions."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.project: Path | None = None
        self.default_vars = {name: tk.StringVar(value="") for name in _ARRANGEMENTS}
        self.status_var = tk.StringVar(value="Open a project to confirm tones and tone regions.")
        self.region_text: dict[str, tk.Text] = {}

        ttk.Label(
            self,
            text=(
                "Confirm the package-facing tone label for Bass, Lead, and Rhythm and any timed tone changes. "
                "Each region line is START_SECONDS | TONE_LABEL. Saving changed authority invalidates stale package staging."
            ),
            wraplength=1080,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        for arrangement in _ARRANGEMENTS:
            frame = ttk.Frame(notebook, padding=10)
            notebook.add(frame, text=arrangement.title())
            ttk.Label(frame, text="Default tone label").grid(row=0, column=0, sticky="w")
            ttk.Entry(frame, textvariable=self.default_vars[arrangement], width=58).grid(
                row=0, column=1, sticky="ew", padx=(8, 0)
            )
            ttk.Label(
                frame,
                text="Tone changes (one per line: START_SECONDS | TONE_LABEL)",
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 4))
            text = tk.Text(frame, height=10, wrap="none", undo=True)
            text.grid(row=2, column=0, columnspan=2, sticky="nsew")
            self.region_text[arrangement] = text
            frame.columnconfigure(1, weight=1)
            frame.rowconfigure(2, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Confirm Tones & Regions", command=self._save).pack(side="left")
        ttk.Button(actions, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))
        ttk.Label(actions, textvariable=self.status_var, wraplength=790).pack(
            side="left", fill="x", expand=True, padx=(14, 0)
        )

        ttk.Label(
            self,
            text=(
                "This surface confirms tone labels and change times only. Detailed amp/effect settings retain their existing "
                "research, audition, and guarded human-approval workflow; this does not approve notes, timing, validation, or installation."
            ),
            wraplength=1080,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

    def set_project(self, project: Path) -> None:
        self.project = project.expanduser().resolve()
        self.refresh()

    def refresh(self) -> None:
        if self.project is None:
            return
        try:
            authority = load_tone_regions(self.project)
        except (OSError, ValueError) as exc:
            self._clear()
            self.status_var.set(f"BLOCKED: {exc}. Re-enter and confirm all three arrangements.")
            return
        if authority is None:
            self._clear()
            self.status_var.set("Enter a default tone for all three arrangements; timed changes are optional.")
            return
        by_name = {item.arrangement: item for item in authority.arrangements}
        for arrangement in _ARRANGEMENTS:
            item = by_name[arrangement]
            self.default_vars[arrangement].set(item.default_tone)
            text = self.region_text[arrangement]
            text.delete("1.0", "end")
            for region in item.regions:
                text.insert("end", f"{region.start_seconds:.3f} | {region.tone_label}\n")
        self.status_var.set(
            "Confirmed for package preparation. Editing a tone label or change time will invalidate stale package staging."
        )

    def _clear(self) -> None:
        for arrangement in _ARRANGEMENTS:
            self.default_vars[arrangement].set("")
            self.region_text[arrangement].delete("1.0", "end")

    def _parse_regions(self, arrangement: str) -> tuple[ToneRegion, ...]:
        regions: list[ToneRegion] = []
        raw = self.region_text[arrangement].get("1.0", "end").strip()
        if not raw:
            return ()
        for line_number, line in enumerate(raw.splitlines(), start=1):
            left, separator, right = line.partition("|")
            if not separator or not right.strip():
                raise ValueError(
                    f"{arrangement.title()} line {line_number}: use START_SECONDS | TONE_LABEL"
                )
            try:
                start = float(left.strip())
            except ValueError as exc:
                raise ValueError(
                    f"{arrangement.title()} line {line_number}: start time must be a number"
                ) from exc
            regions.append(ToneRegion(start_seconds=start, tone_label=right.strip()))
        return tuple(regions)

    def _save(self) -> None:
        if self.project is None:
            return
        try:
            arrangements = tuple(
                ArrangementToneRegions(
                    arrangement=arrangement,
                    default_tone=self.default_vars[arrangement].get().strip(),
                    regions=self._parse_regions(arrangement),
                )
                for arrangement in _ARRANGEMENTS
            )
            confirm_tone_regions(self.project, arrangements=arrangements)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Tones & Regions", str(exc), parent=self)
            self.status_var.set(f"Could not confirm tones/regions: {exc}")
            return
        self.refresh()
        self.status_var.set(
            "Confirmed. Tone-region authority is project-local and stale package state was invalidated if values changed."
        )
