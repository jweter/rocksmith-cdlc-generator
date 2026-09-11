from __future__ import annotations

from tkinter import ttk

from .official_tab_reference import reference_hits_for_role
from .official_tab_reference_ui import OfficialTabReferenceMixin
from .score_source import ArrangementRole


class OfficialTabReferenceRoleMixin(OfficialTabReferenceMixin):
    """Give Official TAB references a role selector independent of authored arrangements.

    Arrangement Preview may legitimately expose only roles with generated arrangement
    drafts. Official TAB references are source evidence and can exist before any draft,
    so their role availability must come from the reference manifest instead.
    """

    def _build_arrangement_preview(self) -> None:
        super()._build_arrangement_preview()
        if not hasattr(self, "official_tab_choice_combo"):
            return

        nav = self.official_tab_choice_combo.master
        ttk.Label(nav, text="Reference").pack(side="left", padx=(10, 4))
        # Reuse the StringVar implementation already provided by tkinter through the
        # existing viewer instead of introducing a second Tk dependency surface.
        self.official_tab_role_var = self.official_tab_choice_var.__class__(value="")
        self.official_tab_role_combo = ttk.Combobox(
            nav,
            textvariable=self.official_tab_role_var,
            state="readonly",
            width=10,
        )
        self.official_tab_role_combo.pack(side="left", padx=(0, 6))
        self.official_tab_role_combo.bind("<<ComboboxSelected>>", self._official_tab_role_changed)
        self._update_official_tab_roles()

    def set_project(self, project) -> None:
        super().set_project(project)
        if hasattr(self, "official_tab_role_var"):
            self.official_tab_role_var.set("")

    def refresh(self) -> None:
        super().refresh()
        self._update_official_tab_roles()
        if hasattr(self, "official_tab_status_var"):
            self._sync_official_tab_reference(force=True)

    def _add_official_tab_page(self) -> None:
        super()._add_official_tab_page()
        self._update_official_tab_roles()
        if hasattr(self, "official_tab_status_var"):
            self._sync_official_tab_reference(force=True)

    def _active_reference_role(self) -> str:
        if hasattr(self, "official_tab_role_var"):
            value = self.official_tab_role_var.get()
            if value in {role.value for role in ArrangementRole}:
                return value
        return super()._active_reference_role()

    def _mapped_reference_roles(self) -> tuple[str, ...]:
        return tuple(
            role.value
            for role in ArrangementRole
            if reference_hits_for_role(self._official_tab_manifest, role)
        )

    def _update_official_tab_roles(self) -> None:
        if not hasattr(self, "official_tab_role_var"):
            return
        roles = self._mapped_reference_roles()
        if hasattr(self, "official_tab_role_combo"):
            self.official_tab_role_combo.configure(values=roles)

        current = self.official_tab_role_var.get()
        if current in roles:
            return

        preview_role = None
        if hasattr(self, "fretboard_role_var"):
            candidate = self.fretboard_role_var.get()
            if candidate in roles:
                preview_role = candidate
        self.official_tab_role_var.set(preview_role or (roles[0] if roles else ""))

    def _official_tab_role_changed(self, _event=None) -> None:
        self._official_tab_manual_key = None
        self._sync_official_tab_reference(force=True)
