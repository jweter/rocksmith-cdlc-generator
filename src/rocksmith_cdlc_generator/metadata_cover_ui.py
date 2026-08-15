from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .build_presentation import (
    build_presentation_cover_path,
    load_build_presentation,
    save_build_presentation,
)
from .metadata_integration import resolve_build_metadata


class MetadataCoverPanel(ttk.Frame):
    """Human-confirmed package metadata and cover selection for one local project."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.project: Path | None = None
        self._selected_cover: Path | None = None

        self.album_var = tk.StringVar(value="")
        self.year_var = tk.StringVar(value="")
        self.cover_var = tk.StringVar(value="No cover selected")
        self.status_var = tk.StringVar(
            value="Open a project to confirm album metadata and cover art."
        )

        intro = ttk.Label(
            self,
            text=(
                "Confirm the package-facing album name, release year, and local cover image. "
                "Saving copies the chosen PNG/JPEG into the private project and invalidates stale package state."
            ),
            wraplength=1120,
            justify="left",
        )
        intro.pack(anchor="w", pady=(0, 12))

        form = ttk.LabelFrame(self, text="Metadata & cover authority", padding=10)
        form.pack(fill="x")
        ttk.Label(form, text="Album", width=14).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.album_var, width=64).grid(
            row=0, column=1, sticky="ew", padx=(6, 8), pady=5
        )
        ttk.Label(form, text="Year", width=14).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=self.year_var, width=12).grid(
            row=1, column=1, sticky="w", padx=(6, 8), pady=5
        )
        ttk.Label(form, text="Cover art", width=14).grid(row=2, column=0, sticky="nw", pady=5)
        cover_row = ttk.Frame(form)
        cover_row.grid(row=2, column=1, sticky="ew", padx=(6, 8), pady=5)
        ttk.Label(cover_row, textvariable=self.cover_var, wraplength=780).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(cover_row, text="Choose PNG/JPEG…", command=self._choose_cover).pack(
            side="right", padx=(8, 0)
        )
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Confirm Metadata & Cover", command=self._save).pack(
            side="left"
        )
        ttk.Button(actions, text="Refresh", command=self.refresh).pack(
            side="left", padx=(6, 0)
        )
        ttk.Label(actions, textvariable=self.status_var, wraplength=800).pack(
            side="left", fill="x", expand=True, padx=(14, 0)
        )

        ttk.Label(
            self,
            text=(
                "This confirmation owns package presentation only. It does not approve musical notes, timing, "
                "fingering, techniques, tones, source rights, validation, package readiness, or installation."
            ),
            wraplength=1120,
            justify="left",
        ).pack(anchor="w", pady=(14, 0))

    def set_project(self, project: Path) -> None:
        self.project = project.expanduser().resolve()
        self._selected_cover = None
        self.refresh()

    def refresh(self) -> None:
        if self.project is None:
            return
        try:
            presentation = load_build_presentation(self.project)
        except (OSError, ValueError, FileNotFoundError) as exc:
            self.album_var.set("")
            self.year_var.set("")
            self.cover_var.set("Saved presentation is invalid")
            self._selected_cover = None
            self.status_var.set(f"BLOCKED: {exc}. Choose metadata/cover and confirm again.")
            return

        if presentation is not None:
            cover = build_presentation_cover_path(self.project, presentation)
            self.album_var.set(presentation.album_name)
            self.year_var.set(str(presentation.year))
            self.cover_var.set(str(cover))
            self._selected_cover = cover
            self.status_var.set(
                "Confirmed for package preparation. Changing these values will invalidate stale package staging."
            )
            return

        self._selected_cover = None
        self.cover_var.set("No cover selected")
        try:
            suggested = resolve_build_metadata(self.project, album_name=None, year=None)
        except (OSError, ValueError, FileNotFoundError):
            self.album_var.set("")
            self.year_var.set("")
            self.status_var.set("Enter album/year, choose local cover art, then confirm.")
        else:
            self.album_var.set(suggested.album_name)
            self.year_var.set(str(suggested.year))
            self.status_var.set(
                "Album/year prefilled from reviewed recording context; confirm them with cover art before packaging."
            )

    def _choose_cover(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Choose local cover art",
            filetypes=[
                ("Cover images", "*.png *.jpg *.jpeg"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return
        self._selected_cover = Path(selected).expanduser().resolve()
        self.cover_var.set(str(self._selected_cover))
        self.status_var.set("Cover selected locally. Confirm to copy it into the project.")

    def _save(self) -> None:
        if self.project is None:
            return
        if self._selected_cover is None:
            messagebox.showwarning(
                "Metadata & Cover",
                "Choose a PNG or JPEG cover image first.",
                parent=self,
            )
            return
        try:
            year = int(self.year_var.get().strip())
        except ValueError:
            messagebox.showerror("Metadata & Cover", "Year must be a whole number.", parent=self)
            return
        try:
            presentation = save_build_presentation(
                self.project,
                album_name=self.album_var.get(),
                year=year,
                cover=self._selected_cover,
            )
            cover = build_presentation_cover_path(self.project, presentation)
        except (OSError, ValueError, FileNotFoundError) as exc:
            messagebox.showerror("Metadata & Cover", str(exc), parent=self)
            self.status_var.set(f"Could not confirm metadata/cover: {exc}")
            return

        self.album_var.set(presentation.album_name)
        self.year_var.set(str(presentation.year))
        self.cover_var.set(str(cover))
        self._selected_cover = cover
        self.status_var.set(
            "Confirmed. Package-facing metadata and cover are project-local and stale package state was invalidated if needed."
        )
