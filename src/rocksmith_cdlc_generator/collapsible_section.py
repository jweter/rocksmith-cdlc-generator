from __future__ import annotations

from tkinter import ttk

#: Plain ASCII-safe marks (not color-dependent, consistent with the #305
#: non-color-alone rule already applied elsewhere in Song Workspace) prefixed to a
#: section's title so its current expand/collapse state is visible in the header
#: itself, not only inferred from whether the body happens to be present.
_EXPANDED_MARK = "▾"  # ▾
_COLLAPSED_MARK = "▸"  # ▸


def collapsible_section_header_text(title: str, *, expanded: bool) -> str:
    """Render a CollapsibleSection header label for the given expand/collapse state."""

    mark = _EXPANDED_MARK if expanded else _COLLAPSED_MARK
    return f"{mark} {title}"


class CollapsibleSection:
    """A user-toggleable Song Workspace review section.

    Issue #563: the Arrangement Preview tab became an "excessively long" scrolling
    page because every secondary review-domain panel (event timing, techniques, chord
    fingering/identity, review queue summary, multi-track composition, edit history)
    packed its controls straight into one always-expanded ``ttk.LabelFrame``, all of
    them fully rendered at once regardless of whether the reviewer is currently working
    on that domain. Existing per-panel "collapse when unavailable" fixes (the
    ``*_content_frame``/``*_unavailable_label`` pattern) already shrink a panel that
    cannot be acted on yet, but do nothing once every panel becomes available -- the
    page is then exactly as long as before.

    ``CollapsibleSection`` is a drop-in replacement for that outer ``ttk.LabelFrame``:
    a clickable header toggles visibility of ``self.body`` (a plain ``ttk.Frame`` with
    the same ``padding`` the old ``LabelFrame`` used), so callers only need to change
    what they pack children into -- every existing child-widget construction and
    ``*_content_frame`` availability toggle keeps working unchanged, since those still
    just pack into (what is now) ``self.body`` and remain part of the same widget tree
    regardless of whether an ancestor is currently displayed.

    This deliberately composes plain ``ttk`` widgets rather than subclassing
    ``ttk.Frame``/``ttk.LabelFrame``: every other Song Workspace panel in this codebase
    constructs widgets via ``ttk.X(parent, ...)`` rather than subclassing a ``tkinter``
    class, which is what lets tests patch ``ttk.Frame``/``ttk.Button`` per-module
    without a real Tk root or display server (subclassing would bind the real
    ``tkinter`` base class at import time, before any test could patch it).
    """

    def __init__(
        self,
        master,
        *,
        text: str,
        expanded: bool = True,
        padding: int = 8,
    ) -> None:
        self._title = text
        self.expanded = expanded

        self.frame = ttk.Frame(master)
        self.toggle_button = ttk.Button(
            self.frame,
            text=collapsible_section_header_text(text, expanded=expanded),
            command=self.toggle,
            style="CollapsibleSectionHeader.TButton",
        )
        self.toggle_button.pack(fill="x")

        self.body = ttk.Frame(self.frame, padding=padding)
        if expanded:
            self.body.pack(fill="x", pady=(4, 0))

    def pack(self, **kwargs: object) -> None:
        self.frame.pack(**kwargs)

    def toggle(self) -> None:
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        self.toggle_button.configure(text=collapsible_section_header_text(self._title, expanded=expanded))
        if expanded:
            self.body.pack(fill="x", pady=(4, 0))
        else:
            self.body.pack_forget()
