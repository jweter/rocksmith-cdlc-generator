from __future__ import annotations

"""Pure presentation logic for the Song Workspace header's project health/progress
indicator.

This is a #305 slice: ``docs/project-status.yaml``'s "Areas to review" list named
"progress indicators" as a still-unadopted #305 surface, and the desktop UI audit
(``docs/ui/desktop-ui-audit.md`` finding #2) found status text like ``"BLOCKED"``/
``"READY"`` renders everywhere as plain, unstyled text. The Song Workspace header's
project-health line (``SongWorkspaceWindow.health_var``, built from
``SongWorkspaceSnapshot.health``) and its ``ttk.Progressbar`` (``self.progress``) are
exactly that: a plain ``WorkspaceHealth`` string with no color, symbol, or weight
differentiation, and a progress bar that renders identically whether the project is
newly started, actively in progress, blocked on a validation failure, or ready to
package. This mirrors the pattern already established for the Review Queue severity
column (``review_queue_row_presentation.py``) and the Score & Mappings role status
(``score_mapping_status_presentation.py``): turn domain state into a semantic
``StatusState`` plus ready-to-render text/style in a tkinter-free module.

This module defines no new workflow/health authority. ``SongWorkspaceSnapshot.health``
is computed exactly as before (see ``song_workspace.build_song_workspace_snapshot``);
this only maps that existing value to the shared semantic status vocabulary so it can
be rendered with the same non-color-alone (symbol + label + color) treatment used
everywhere else, including a matching color on the progress bar itself.
"""

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status

#: SongWorkspaceSnapshot.health is WorkspaceHealth = Literal["NEW", "IN_PROGRESS",
#: "REVIEW", "BLOCKED", "READY"] (song_workspace.py). BLOCKED means a validation
#: problem/failure exists (fail); REVIEW means a human-blocking workflow step is
#: outstanding (review_required); READY means every configured arrangement has
#: exported XML and no required work remains (pass); NEW and IN_PROGRESS are both
#: ordinary, non-actionable progress states with nothing to review yet (info).
_HEALTH_TO_STATUS_STATE: dict[str, StatusState] = {
    "BLOCKED": "fail",
    "REVIEW": "review_required",
    "READY": "pass",
    "NEW": "info",
    "IN_PROGRESS": "info",
}

#: Short, stable detail text for each health value. Kept separate from the raw
#: WorkspaceHealth string (which stays visible via format_status's label/symbol) so
#: the header reads as a sentence instead of a bare enum value.
_HEALTH_DETAIL: dict[str, str] = {
    "BLOCKED": "Blocked — validation problems must be resolved",
    "REVIEW": "Awaiting human review",
    "READY": "Ready — workflow complete, exports ready",
    "NEW": "New project — no steps completed yet",
    "IN_PROGRESS": "In progress",
}


class WorkspaceHealthPresentation(BaseModel):
    """Presentation-only status for the Song Workspace header's health/progress row."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    health_text: str
    progressbar_style: str


def progressbar_style_name(state: StatusState) -> str:
    """ttk style name for the semantic-status ``Horizontal.TProgressbar`` variant.

    A plain string helper (no ``tkinter`` import) so it stays unit-testable without a
    display server; the caller registers the actual style via
    ``ttk.Style().configure(name, background=...)`` against a live ``ttk.Style``.
    """

    return f"Status.{state.title().replace('_', '')}.Horizontal.TProgressbar"


def present_workspace_health(health: str) -> WorkspaceHealthPresentation:
    """Classify one ``SongWorkspaceSnapshot.health`` value for header presentation.

    Unrecognized health values (defensive only -- ``WorkspaceHealth`` is a ``Literal``
    so normal callers cannot produce one) fall back to ``"info"`` rather than raising,
    so an unexpected future health value still renders instead of breaking the header.
    """

    state = _HEALTH_TO_STATUS_STATE.get(health, "info")
    detail = _HEALTH_DETAIL.get(health, health.replace("_", " ").title())
    return WorkspaceHealthPresentation(
        status_state=state,
        health_text=format_status(state, detail),
        progressbar_style=progressbar_style_name(state),
    )
