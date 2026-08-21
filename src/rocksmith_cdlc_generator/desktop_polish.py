from __future__ import annotations

"""Presentation-only structural polish for existing Tk/ttk widget trees.

The legacy desktop screens were built before the shared design system and therefore
mostly use unnamed ttk styles. This adapter lets those screens adopt the new visual
language without rewriting workflow code or inferring/changing any domain state.
"""

from typing import Any

from .desktop_theme import PALETTE


_PRIMARY_ACTION_LABELS = frozenset(
    {
        "Continue Automatically",
        "Next Step",
        "Run Safe Automatic Steps",
    }
)


def polish_widget_tree(root: Any) -> None:
    """Apply named presentation styles to an existing Tk/ttk widget tree.

    Styling decisions depend only on widget type, containment, and a deliberately
    small allow-list of already-existing primary action labels. Commands, variables,
    enabled state, data, and review authority are never modified.
    """

    import tkinter as tk
    from tkinter import ttk

    def visit(widget: Any, *, surface_context: bool = False) -> None:
        current_surface = surface_context

        if isinstance(widget, ttk.LabelFrame):
            current_surface = True
        elif isinstance(widget, ttk.Frame) and surface_context:
            widget.configure(style="Surface.TFrame")
        elif isinstance(widget, ttk.Label) and surface_context:
            widget.configure(style="Surface.TLabel")
        elif isinstance(widget, ttk.Button):
            try:
                text = str(widget.cget("text"))
            except Exception:
                text = ""
            if text in _PRIMARY_ACTION_LABELS:
                widget.configure(style="Primary.TButton")
        elif isinstance(widget, tk.Text):
            widget.configure(
                background=PALETTE.surface,
                foreground=PALETTE.text,
                insertbackground=PALETTE.text,
                selectbackground=PALETTE.selection,
                selectforeground=PALETTE.text,
                relief="flat",
                highlightthickness=1,
                highlightbackground=PALETTE.border,
                highlightcolor=PALETTE.accent,
            )
        elif isinstance(widget, tk.Canvas):
            widget.configure(
                background=PALETTE.surface,
                highlightthickness=1,
                highlightbackground=PALETTE.border,
            )

        for child in widget.winfo_children():
            visit(child, surface_context=current_surface)

    visit(root)
