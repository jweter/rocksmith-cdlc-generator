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

_TRANSPORT_ACTION_LABELS = frozenset(
    {
        "Play",
        "Stop",
        "First note",
        "Previous issue",
        "Next issue",
        "◀ Page",
        "Page ▶",
    }
)

_UTILITY_ACTION_LABELS = frozenset(
    {
        "Refresh",
        "Show Official TAB",
        "Show Highway",
        "Open in EOF",
        "Compare alternate GP…",
        "Fit width",
        "Zoom −",
        "Zoom +",
    }
)

_REVIEW_AID_LABELS = {
    "Variable-tempo click": "Click Track · Audition Beat Grid",
}


def configure_polish_styles(style: Any) -> None:
    """Register the higher-contrast workspace chrome used by ``polish_widget_tree``.

    The styles are presentation-only. They deliberately do not encode workflow state;
    semantic PASS/WARNING/FAIL styling remains owned by ``desktop_theme``.
    """

    style.configure(
        "Workspace.TNotebook",
        background=PALETTE.canvas,
        bordercolor=PALETTE.border,
        borderwidth=0,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "Workspace.TNotebook.Tab",
        background=PALETTE.canvas,
        foreground=PALETTE.text_muted,
        padding=(18, 10),
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
    )
    style.map(
        "Workspace.TNotebook.Tab",
        background=[("selected", PALETTE.accent_soft), ("active", PALETTE.surface_alt)],
        foreground=[("selected", PALETTE.accent_hover), ("active", PALETTE.text)],
    )

    style.configure(
        "Workspace.Treeview",
        background=PALETTE.surface,
        fieldbackground=PALETTE.surface,
        foreground=PALETTE.text,
        rowheight=32,
        bordercolor=PALETTE.border,
        borderwidth=1,
        relief="flat",
        font=("Segoe UI", 10),
    )
    style.map(
        "Workspace.Treeview",
        background=[("selected", PALETTE.selection)],
        foreground=[("selected", PALETTE.text)],
    )
    style.configure(
        "Workspace.Treeview.Heading",
        background=PALETTE.surface_alt,
        foreground=PALETTE.text,
        bordercolor=PALETTE.border,
        relief="flat",
        padding=(10, 8),
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Workspace.Treeview.Heading",
        background=[("active", PALETTE.border)],
        foreground=[("active", PALETTE.text)],
    )

    style.configure(
        "Transport.TButton",
        background=PALETTE.accent_soft,
        foreground=PALETTE.text,
        bordercolor=PALETTE.border_strong,
        padding=(12, 6),
        font=("Segoe UI", 9, "bold"),
        relief="flat",
    )
    style.map(
        "Transport.TButton",
        background=[("pressed", PALETTE.accent_pressed), ("active", PALETTE.selection)],
        bordercolor=[("focus", PALETTE.accent), ("active", PALETTE.accent)],
        foreground=[("disabled", PALETTE.text_muted)],
    )

    style.configure(
        "Utility.TButton",
        background=PALETTE.surface,
        foreground=PALETTE.text_muted,
        bordercolor=PALETTE.border,
        padding=(10, 6),
        font=("Segoe UI", 9, "bold"),
        relief="flat",
    )
    style.map(
        "Utility.TButton",
        background=[("pressed", PALETTE.selection), ("active", PALETTE.surface_alt)],
        bordercolor=[("focus", PALETTE.accent), ("active", PALETTE.border_strong)],
        foreground=[("active", PALETTE.text), ("disabled", PALETTE.text_muted)],
    )

    for orientation in ("Vertical", "Horizontal"):
        style.configure(
            f"Workspace.{orientation}.TScrollbar",
            background=PALETTE.border_strong,
            troughcolor=PALETTE.canvas,
            bordercolor=PALETTE.canvas,
            arrowcolor=PALETTE.text_muted,
            relief="flat",
        )
        style.map(
            f"Workspace.{orientation}.TScrollbar",
            background=[("active", PALETTE.accent), ("pressed", PALETTE.accent_pressed)],
            arrowcolor=[("active", PALETTE.text)],
        )

    style.configure(
        "Workspace.TPanedwindow",
        background=PALETTE.border,
        sashrelief="flat",
        sashwidth=7,
    )


def polish_widget_tree(root: Any) -> None:
    """Apply named presentation styles to an existing Tk/ttk widget tree.

    Styling decisions depend only on widget type, containment, and a deliberately
    small allow-list of already-existing presentation labels. Commands, variables,
    enabled state, data, and review authority are never modified.
    """

    import tkinter as tk
    from tkinter import ttk

    configure_polish_styles(ttk.Style(root))

    def visit(widget: Any, *, surface_context: bool = False) -> None:
        current_surface = surface_context

        if isinstance(widget, ttk.LabelFrame):
            current_surface = True
        elif isinstance(widget, ttk.Frame) and surface_context:
            widget.configure(style="Surface.TFrame")
        elif isinstance(widget, ttk.Label) and surface_context:
            widget.configure(style="Surface.TLabel")
        elif isinstance(widget, ttk.Notebook):
            widget.configure(style="Workspace.TNotebook")
        elif isinstance(widget, ttk.Treeview):
            widget.configure(style="Workspace.Treeview")
        elif isinstance(widget, ttk.Panedwindow):
            widget.configure(style="Workspace.TPanedwindow")
        elif isinstance(widget, ttk.Scrollbar):
            try:
                orientation = str(widget.cget("orient")).lower()
            except Exception:
                orientation = "vertical"
            prefix = "Horizontal" if orientation.startswith("h") else "Vertical"
            widget.configure(style=f"Workspace.{prefix}.TScrollbar")
        elif isinstance(widget, ttk.Button):
            try:
                text = str(widget.cget("text"))
            except Exception:
                text = ""
            if text in _PRIMARY_ACTION_LABELS:
                widget.configure(style="Primary.TButton", cursor="hand2")
            elif text in _TRANSPORT_ACTION_LABELS:
                widget.configure(style="Transport.TButton", cursor="hand2")
            elif text in _UTILITY_ACTION_LABELS:
                widget.configure(style="Utility.TButton", cursor="hand2")
            else:
                widget.configure(cursor="hand2")
        elif isinstance(widget, ttk.Checkbutton):
            try:
                text = str(widget.cget("text"))
            except Exception:
                text = ""
            replacement = _REVIEW_AID_LABELS.get(text)
            if replacement is not None:
                widget.configure(text=replacement, style="ReviewAid.TCheckbutton", cursor="hand2")
            else:
                widget.configure(cursor="hand2")
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
