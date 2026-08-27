from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .official_tab_reference import (
    load_reference_manifest,
    reference_hits_for_role,
    register_reference_page,
)
from .score_source import ArrangementRole


class _MultiArrangementReferenceDialog(tk.Toplevel):
    """Map one photographed page to every arrangement represented on that page."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        active_role: str,
        first_measure: int,
        last_measure: int,
    ) -> None:
        super().__init__(parent)
        self.title("Map official TAB page")
        self.resizable(False, False)
        self.transient(parent)
        self.result: tuple[tuple[ArrangementRole, ...], int, int, str | None] | None = None

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(
                "Select every arrangement represented anywhere on this private page image. "
                "The same photograph can reference Bass, Lead, and Rhythm without importing it again."
            ),
            wraplength=560,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Label(frame, text="Arrangements on this page").grid(row=1, column=0, sticky="nw", pady=4)
        role_box = ttk.Frame(frame)
        role_box.grid(row=1, column=1, sticky="w", pady=4)
        active = active_role if active_role in {role.value for role in ArrangementRole} else "lead"
        self.role_vars: dict[ArrangementRole, tk.BooleanVar] = {}
        for role in (ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm):
            var = tk.BooleanVar(value=role.value == active)
            self.role_vars[role] = var
            ttk.Checkbutton(role_box, text=role.value.title(), variable=var).pack(side="left", padx=(0, 12))

        ttk.Label(frame, text="First score bar").grid(row=2, column=0, sticky="w", pady=4)
        self.first_var = tk.StringVar(value=str(max(first_measure, 1)))
        ttk.Spinbox(frame, from_=1, to=10000, width=12, textvariable=self.first_var).grid(
            row=2, column=1, sticky="w", pady=4
        )

        ttk.Label(frame, text="Last score bar").grid(row=3, column=0, sticky="w", pady=4)
        self.last_var = tk.StringVar(value=str(max(last_measure, first_measure, 1)))
        ttk.Spinbox(frame, from_=1, to=10000, width=12, textvariable=self.last_var).grid(
            row=3, column=1, sticky="w", pady=4
        )

        ttk.Label(frame, text="Printed page label (optional)").grid(row=4, column=0, sticky="w", pady=4)
        self.page_var = tk.StringVar(value="")
        ttk.Entry(frame, textvariable=self.page_var, width=24).grid(row=4, column=1, sticky="ew", pady=4)

        ttk.Label(
            frame,
            text=(
                "These bar numbers describe where the page belongs on the shared score timeline; "
                "they do not claim every selected arrangement plays in every bar."
            ),
            wraplength=560,
            justify="left",
            style="Muted.TLabel",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Add Reference", command=self._accept).pack(side="right", padx=(0, 8))

        frame.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._accept())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.after_idle(self._center_on_parent)

    def _center_on_parent(self) -> None:
        try:
            self.update_idletasks()
            parent = self.master
            x = parent.winfo_rootx() + max((parent.winfo_width() - self.winfo_width()) // 2, 0)
            y = parent.winfo_rooty() + max((parent.winfo_height() - self.winfo_height()) // 2, 0)
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            return

    def _accept(self) -> None:
        try:
            roles = tuple(role for role, var in self.role_vars.items() if var.get())
            if not roles:
                raise ValueError("Select at least one arrangement represented on this page.")
            first = int(self.first_var.get())
            last = int(self.last_var.get())
            if first < 1 or last < first:
                raise ValueError("Last score bar must be greater than or equal to first score bar.")
        except (TypeError, ValueError) as exc:
            messagebox.showerror("Official TAB Reference", str(exc), parent=self)
            return
        page = self.page_var.get().strip() or None
        self.result = (roles, first, last, page)
        self.destroy()


class MultiArrangementOfficialTabMixin:
    """Upgrade OfficialTabReferenceMixin's Add page flow to multi-role checkboxes."""

    @staticmethod
    def _validate_reference_ranges_available(manifest, roles, first: int, last: int) -> None:
        for role in roles:
            for hit in reference_hits_for_role(manifest, role):
                existing_start = hit.mapping.measure_start
                existing_end = hit.mapping.measure_end
                if first <= existing_end and existing_start <= last:
                    raise ValueError(
                        f"{role.value.title()} already has an official TAB mapping for bars "
                        f"{existing_start}-{existing_end}. Adjust the page range before adding it."
                    )

    def _add_official_tab_page(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self,
            title="Add official TAB reference page",
            filetypes=(
                ("TAB page images", "*.jpg *.jpeg *.png"),
                ("JPEG images", "*.jpg *.jpeg"),
                ("PNG images", "*.png"),
            ),
        )
        if not filename:
            return

        current = self._current_reference_measure() or 1
        last_known = self._eof_measure_windows[-1].number if getattr(self, "_eof_measure_windows", []) else current
        suggested_last = min(current + 7, last_known)
        dialog = _MultiArrangementReferenceDialog(
            self,
            active_role=self._active_reference_role(),
            first_measure=current,
            last_measure=max(suggested_last, current),
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return

        roles, first, last, page_label = dialog.result
        try:
            manifest = load_reference_manifest(self.project, verify_files=True)
            self._validate_reference_ranges_available(manifest, roles, first, last)
            hits = [
                register_reference_page(
                    self.project,
                    Path(filename),
                    arrangement=role,
                    measure_start=first,
                    measure_end=last,
                    printed_page=page_label,
                )
                for role in roles
            ]
            self._official_tab_manifest = load_reference_manifest(self.project, verify_files=True)
        except Exception as exc:
            messagebox.showerror("Official TAB Reference", str(exc), parent=self)
            return

        self._official_tab_error = None
        active_role = self._active_reference_role()
        hit = next((item for item in hits if item.mapping.arrangement.value == active_role), hits[0])
        self._official_tab_current_hit = hit
        self._official_tab_manual_key = self._hit_key(hit)
        self._official_tab_last_render_key = None
        self._set_official_tab_visible(True, user_choice=True)
        self._sync_official_tab_reference(force=True)
