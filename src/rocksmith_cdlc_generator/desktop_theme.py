from __future__ import annotations

"""Centralized visual theme for the packaged Windows authoring application.

The project deliberately keeps visual styling separate from workflow, review,
provenance, validation, and packaging authority. This module only configures Tk/ttk
presentation. It can therefore evolve without changing what any button is allowed to
do or what any status means.
"""

from dataclasses import dataclass
from typing import Any

from .design_tokens import STATUS_STYLES, TYPOGRAPHY, StatusState, configure_ttk_status_styles, spacing


@dataclass(frozen=True)
class DesktopPalette:
    """Dark-first studio/workbench color tokens for long authoring sessions."""

    canvas: str = "#0E1116"
    surface: str = "#151A22"
    surface_alt: str = "#1D2430"
    border: str = "#2B3442"
    border_strong: str = "#3A4658"
    text: str = "#E8EDF5"
    text_muted: str = "#9AA8BA"
    accent: str = "#7C6CF2"
    accent_hover: str = "#8F82F5"
    accent_pressed: str = "#6254D8"
    accent_soft: str = "#24213F"
    selection: str = "#302A63"
    success: str = "#55D98D"
    warning: str = "#F2BD5A"
    danger: str = "#FF746C"
    info: str = "#B7C4D6"


PALETTE = DesktopPalette()
_THEME_NAME = "clam"

#: ``design_tokens.STATUS_STYLES`` foregrounds are chosen for readable contrast on
#: the *light* backgrounds ttk's native Windows themes use (see that module's own
#: docstring). This app is dark-first (``PALETTE`` above), so any call site that sets
#: a status label's ``foreground`` directly -- rather than applying the named
#: ``status.ttk_style_name`` ``configure_desktop_styles`` already registers with the
#: correct dark-theme color below -- must resolve through this mapping instead of
#: ``design_tokens.status_style(...).foreground``. Using the light-token color
#: directly on the dark ``PALETTE.surface``/``PALETTE.canvas`` background produces
#: near-unreadable low-contrast text (e.g. ``status_style("pass").foreground``
#: ``#1B5E20`` dark green on ``PALETTE.surface`` ``#151A22``); this is the same
#: contrast defect the Song Workspace header health/progress indicator and Review
#: Queue severity column were fixed for, applied to every other status label so the
#: fix lives in one place instead of being re-copied per screen.
_DARK_STATUS_FOREGROUNDS: dict[StatusState, str] = {
    "pass": PALETTE.success,
    "warning": PALETTE.warning,
    "fail": PALETTE.danger,
    "stale": PALETTE.text_muted,
    "review_required": PALETTE.accent_hover,
    "info": PALETTE.info,
}


def status_dark_foreground(state: StatusState) -> str:
    """Return the dark-theme-contrast-safe foreground for a semantic status state.

    Prefer this over ``design_tokens.status_style(state).foreground`` in any desktop
    screen that sets a label's ``foreground`` directly, since that token is tuned for
    light backgrounds and reads as low-contrast-to-illegible on this app's dark
    ``PALETTE``.
    """

    return _DARK_STATUS_FOREGROUNDS[state]


def _font(name: str) -> tuple[str, int] | tuple[str, int, str]:
    return TYPOGRAPHY[name].as_tuple()


def configure_desktop_styles(style: Any) -> None:
    """Configure the shared dark ttk style registry.

    ``style`` intentionally uses a structural type so this function can be exercised
    by pure tests without importing Tk. A real caller passes ``ttk.Style(root)``.
    """

    palette = PALETTE

    style.configure("TFrame", background=palette.surface)
    style.configure("Surface.TFrame", background=palette.surface)
    style.configure("Card.TFrame", background=palette.surface)

    style.configure(
        "TLabel",
        background=palette.surface,
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
        background=palette.surface,
        foreground=palette.text_muted,
        font=_font("caption"),
    )
    style.configure(
        "Title.TLabel",
        background=palette.surface,
        foreground=palette.text,
        font=_font("display"),
    )
    style.configure(
        "Heading.TLabel",
        background=palette.surface,
        foreground=palette.text,
        font=_font("heading"),
    )
    style.configure(
        "Subheading.TLabel",
        background=palette.surface,
        foreground=palette.text,
        font=_font("subheading"),
    )

    style.configure(
        "TLabelframe",
        background=palette.surface,
        bordercolor=palette.border,
        lightcolor=palette.border,
        darkcolor=palette.border,
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
        background=palette.surface_alt,
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
        background=[
            ("pressed", palette.selection),
            ("active", palette.border),
            ("disabled", palette.surface),
        ],
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
        foreground=[("disabled", palette.text_muted)],
        bordercolor=[("active", palette.accent_hover)],
    )

    style.configure(
        "TNotebook",
        background=palette.canvas,
        bordercolor=palette.border,
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
        foreground=[("selected", palette.accent_hover), ("active", palette.text)],
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
        background=[("active", palette.border)],
        foreground=[("active", palette.text)],
    )

    for entry_style in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            entry_style,
            fieldbackground=palette.surface_alt,
            foreground=palette.text,
            bordercolor=palette.border_strong,
            lightcolor=palette.border_strong,
            darkcolor=palette.border_strong,
            arrowcolor=palette.text_muted,
            insertcolor=palette.text,
            padding=spacing("sm"),
        )
        style.map(
            entry_style,
            fieldbackground=[("readonly", palette.surface_alt)],
            foreground=[("readonly", palette.text), ("disabled", palette.text_muted)],
            bordercolor=[("focus", palette.accent)],
            lightcolor=[("focus", palette.accent)],
            darkcolor=[("focus", palette.accent)],
            arrowcolor=[("active", palette.text)],
        )

    style.configure(
        "Horizontal.TProgressbar",
        background=palette.accent,
        troughcolor=palette.border,
        bordercolor=palette.border,
        lightcolor=palette.accent,
        darkcolor=palette.accent,
        borderwidth=0,
        thickness=10,
    )

    style.configure("TSeparator", background=palette.border)
    style.configure(
        "TCheckbutton",
        background=palette.surface,
        foreground=palette.text,
        font=_font("body"),
    )
    style.map(
        "TCheckbutton",
        background=[("active", palette.surface)],
        foreground=[("disabled", palette.text_muted)],
    )
    style.configure(
        "ReviewAid.TCheckbutton",
        background=palette.accent_soft,
        foreground=palette.accent_hover,
        font=_font("body_bold"),
        padding=(spacing("md"), spacing("sm")),
    )
    style.map(
        "ReviewAid.TCheckbutton",
        background=[("active", palette.selection)],
        foreground=[("active", palette.text), ("disabled", palette.text_muted)],
    )

    configure_ttk_status_styles(style)
    for state, status in STATUS_STYLES.items():
        style.configure(
            status.ttk_style_name,
            background=palette.surface,
            foreground=status_dark_foreground(state),
        )


def _style_existing_menu(root: Any) -> None:
    """Darken the already-created application menu tree when one is present."""

    import tkinter as tk

    try:
        menu_name = root.cget("menu")
        if not menu_name:
            return
        menu = root.nametowidget(menu_name)
    except Exception:
        return

    def visit(current: Any) -> None:
        if not isinstance(current, tk.Menu):
            return
        current.configure(
            background=PALETTE.surface,
            foreground=PALETTE.text,
            activebackground=PALETTE.selection,
            activeforeground=PALETTE.text,
            disabledforeground=PALETTE.text_muted,
            relief="flat",
            borderwidth=0,
        )
        for child in current.winfo_children():
            visit(child)

    visit(menu)


def apply_desktop_theme(root: Any) -> str:
    """Apply the dark-first desktop theme to a live Tk root.

    The bundled ``clam`` ttk theme is selected when available because it consistently
    honors custom colors on Windows, unlike native themes that may ignore requested
    backgrounds. If it is unavailable, the current platform theme remains active and
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
    _style_existing_menu(root)

    return style.theme_use()
