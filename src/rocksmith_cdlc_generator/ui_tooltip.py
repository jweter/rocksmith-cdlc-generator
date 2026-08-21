from __future__ import annotations

"""Minimal, dependency-free tooltip helper for the Tkinter/ttk desktop authoring
workspace.

This is a small, focused #305 discoverability primitive (see
``docs/project-status.yaml`` and the issue #305 Product Reality feedback asking for
a short tooltip on the timing-review click-track control): a short delayed popup
that explains what a control does, without adding any new musical, provenance, or
review authority and without every UI module that wants a tooltip hand-rolling one.

Unlike ``design_tokens.py`` (deliberately importable without ``tkinter`` so pure
status logic stays testable without a display server), this module requires
``tkinter`` -- any caller attaching a tooltip already imports ``tkinter``/``ttk`` to
build the widget being annotated.
"""

import tkinter as tk
from tkinter import ttk

from .design_tokens import TYPOGRAPHY

#: Hover delay before the popup appears. Long enough that moving the pointer across
#: a toolbar does not flash popups; short enough that a deliberate hover is fast.
DEFAULT_DELAY_MS = 500


class Tooltip:
    """Attach a short delayed explanatory popup to one widget.

    Hovering ``widget`` for ``delay_ms`` shows ``text`` in a small borderless
    top-level positioned just below the widget. The popup disappears on
    mouse-leave, any button press, or when the host widget is destroyed. This is
    explanatory text only -- it never blocks input, changes focus, or carries any
    review/provenance/validation authority.
    """

    def __init__(self, widget: tk.Widget, text: str, *, delay_ms: int = DEFAULT_DELAY_MS) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: str | None = None
        self._popup: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._cancel_pending()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._popup is not None or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        popup = tk.Toplevel(self.widget)
        popup.wm_overrideredirect(True)
        try:
            popup.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        popup.wm_geometry(f"+{x}+{y}")
        ttk.Label(
            popup,
            text=self.text,
            background="#FFFFE1",
            foreground="#000000",
            relief="solid",
            borderwidth=1,
            padding=(6, 3),
            font=TYPOGRAPHY["caption"].as_tuple(),
            wraplength=320,
            justify="left",
        ).pack()
        self._popup = popup

    def _hide(self, _event: tk.Event | None = None) -> None:
        self._cancel_pending()
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None
