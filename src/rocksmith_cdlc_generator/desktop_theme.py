from __future__ import annotations

"""Centralized visual theme for the packaged Windows authoring application.

The project deliberately keeps visual styling separate from workflow, review,
provenance, validation, and packaging authority.  This module only configures Tk/ttk
presentation.  It can therefore evolve without changing what any button is allowed to
do or what any status means.
"""

from dataclasses import dataclass
from typing import Any

from .design_tokens import TYPOGRAPHY, configure_ttk_status_styles, spacing


@dataclass(frozen=True)
class DesktopPalette:
    """Color tokens for the light studio/workbench theme."""

    canvas: str = "#F3F5F8"
    surface: str = "#FFFFFF"
    surface_alt: str = "#F8FAFC"
    border: str = "#D9E0EA"
    border_strong: str = "#C2CCD9"
    text: str = "#182230"
    text_muted: str = "#607084"
    accent: str = "#5856D6"
    accent_hover: str = "#4745C4"
    accent_pressed: str = "#3E3CAB"
    accent_soft: str = "#EFEEFF"
    selection: str = "#E7E6FF"
    success: str = "#1B7F45"
    warning: str = "#9B6500"
    danger: str = "#B42318"


PALETTE = DesktopPalette()
_THEME_NAME = "clam"


def _font(name: str) -> tuple[str, int] | tuple[str, int, str]:
    return TYPOGRAPHY[name].as_tuple()


def configure_desktop_styles(style: Any) -> None:
    """Configure the shared ttk style registry.

    ``style`` intentionally uses a structural type so this function can be exercised
    by pure tests without importing Tk.  A real caller passes ``ttk.Style(root)``.
    """

    palette = PALETTE

    style.configure("TFrame", background=palette.canvas)
    style.configure("Surface.TFrame", background=palette.surface)
    style.configure("Card.TFrame", background=palette.surface)

    style.configure(
        "TLabel",
        background=palette.canvas,
        foreground=palette.text,
        font=_font("body"),
    )
    style.configure(
        "Surface.TLabel",
        background=palette.surface,
        foreground=palette.text,
        font=_font("body"),
    )
    style.configure(
        "Muted.TLabel",
        background=palette.canvas,
        foreground=palette.text_muted,
        font=_font("caption"),
    )
    style.configure(
        "Title.TLabel",
        background=palette.canvas,
        foreground=palette.text,
        font=_font("display"),
    )
    style.configure(
        "Heading.TLabel",
        background=palette.canvas,
        foreground=palette.text,
        font=_font("heading"),
    )
    style.configure(
        "Subheading.TLabel",
        background=palette.canvas,
        foreground=palette.text,
        font=_font("subheading"),
    )

    style.configure(
        "TLabelframe",
        background=palette.surface,
        bordercolor=palette.border,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=palette.surface,
        foreground=palette.text,
        font=_font("body_bold"),
    )

    style.configure(
        "TButton",
        background=palette.surface,
        foreground=palette.text,
        bordercolor=palette.border_strong,
        focusthickness=1,
        focuscolor=palette.accent,
        padding=(spacing("md"), spacing("sm")),
        font=_font("body_bold"),
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("pressed", palette.selection), ("active", palette.surface_alt)],
        bordercolor=[("focus", palette.accent), ("active", palette.border_strong)],
        foreground=[("disabled", palette.text_muted)],
    )

    style.configure(
        "Primary.TButton",
        background=palette.accent,
        foreground="#FFFFFF",
        bordercolor=palette.accent,
        padding=(spacing("lg"), spacing("sm")),
        font=_font("body_bold"),
        relief="flat",
    )
    style.map(
        "Primary.TButton",
        background=[
            ("pressed", palette.accent_pressed),
            ("active", palette.accent_hover),
            ("disabled", palette.border_strong),
        ],
        foreground=[("disabled", palette.surface_alt)],
        bordercolor=[("active", palette.accent_hover)],
    )

    style.configure(
        "TNotebook",
        background=palette.canvas,
        borderwidth=0,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=palette.canvas,
        foreground=palette.text_muted,
        padding=(spacing("lg"), spacing("md")),
        font=_font("body_bold"),
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", palette.surface), ("active", palette.surface_alt)],
        foreground=[("selected", palette.accent), ("active", palette.text)],
        expand=[("selected", (0, 0, 0, spacing("xs")))],
    )

    style.configure(
        "Treeview",
        background=palette.surface,
        fieldbackground=palette.surface,
        foreground=palette.text,
        rowheight=30,
        bordercolor=palette.border,
        borderwidth=1,
        relief="flat",
        font=_font("body"),
    )
    style.map(
        "Treeview",
        background=[("selected", palette.selection)],
        foreground=[("selected", palette.text)],
    )
    style.configure(
        "Treeview.Heading",
        background=palette.surface_alt,
        foreground=palette.text_muted,
        bordercolor=palette.border,
        relief="flat",
        padding=(spacing("sm"), spacing("sm")),
        font=_font("body_bold"),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", palette.selection)],
        foreground=[("active", palette.text)],
    )

    for entry_style in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            entry_style,
            fieldbackground=palette.surface,
            foreground=palette.text,
            bordercolor=palette.border_strong,
            lightcolor=palette.border_strong,
            darkcolor=palette.border_strong,
            padding=spacing("sm"),
        )
        style.map(
            entry_style,
            bordercolor=[("focus", palette.accent)],
            lightcolor=[("focus", palette.accent)],
            darkcolor=[("focus", palette.accent)],
        )

    style.configure(
        "Horizontal.TProgressbar",
        background=palette.accent,
        troughcolor=palette.border,
        borderwidth=0,
        thickness=10,
    )

    style.configure(
        "TSeparator",
        background=palette.border,
    )

    configure_ttk_status_styles(style)


def apply_desktop_theme(root: Any) -> str:
    """Apply the modern desktop theme to a live Tk root and return the theme name.

    The bundled ``clam`` ttk theme is selected when available because it consistently
    honors custom colors on Windows, unlike native themes that may ignore requested
    backgrounds.  If it is unavailable, the current platform theme remains active and
    the same style registry is still applied.
    """

    from tkinter import ttk

    palette = PALETTE
    style = ttk.Style(root)
    available = set(style.theme_names())
    if _THEME_NAME in available:
        style.theme_use(_THEME_NAME)

    configure_desktop_styles(style)

    root.configure(background=palette.canvas)
    root.option_add("*Font", _font("body"))
    root.option_add("*Background", palette.canvas)
    root.option_add("*Foreground", palette.text)
    root.option_add("*selectBackground", palette.selection)
    root.option_add("*selectForeground", palette.text)
    root.option_add("*Text.background", palette.surface)
    root.option_add("*Text.foreground", palette.text)
    root.option_add("*Text.insertBackground", palette.text)
    root.option_add("*Text.selectBackground", palette.selection)
    root.option_add("*Canvas.background", palette.surface)
    root.option_add("*Menu.background", palette.surface)
    root.option_add("*Menu.foreground", palette.text)
    root.option_add("*Menu.activeBackground", palette.selection)
    root.option_add("*Menu.activeForeground", palette.text)

    return style.theme_use()
