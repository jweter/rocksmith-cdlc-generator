from __future__ import annotations

"""Shared desktop design-system foundation: typography, spacing, and semantic status
styling tokens for the Tkinter/ttk Windows authoring workspace.

This is the first #305 slice ("a small design-system foundation") and is deliberately
narrow: it defines *tokens* other UI modules can adopt, plus one helper that applies
the semantic status styles to a live ``ttk.Style``. It does not retrofit any existing
window (that is a later, separate #305 slice — see ``PROJECT_PLAN.md``), and it defines
no new musical/provenance/review authority.

Every semantic status pairs a color with a distinct symbol *and* label text so no
status is ever conveyed by color alone (colorblind-safe, and legible in any ttk theme
that overrides foreground colors). ``STALE`` additionally renders in italic so an
out-of-date value stays visually unmistakable even at a glance -- see #305 and the
review-gate expectations in ``docs/project-status.yaml``.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FontWeight = Literal["normal", "bold"]
FontSlant = Literal["roman", "italic"]

#: Single font family used across the desktop app today (see e.g. desktop_shell.py,
#: song_workspace_ui.py). Kept as one named constant instead of a literal string
#: scattered across call sites.
FONT_FAMILY = "Segoe UI"


class TypeStyle(BaseModel):
    """One named point on the typography scale."""

    model_config = ConfigDict(frozen=True)

    family: str = FONT_FAMILY
    size: int = Field(gt=0)
    weight: FontWeight = "normal"
    slant: FontSlant = "roman"

    def as_tuple(self) -> tuple[str, int, str] | tuple[str, int]:
        """Return the ``font=`` tuple ``tkinter``/``ttk`` widgets accept."""

        parts = [self.weight] if self.weight != "normal" else []
        if self.slant == "italic":
            parts.append("italic")
        if parts:
            return (self.family, self.size, " ".join(parts))
        return (self.family, self.size)


#: Typography scale. ``DISPLAY``, ``SUBHEADING``, and ``BODY`` formalize sizes already
#: observed in use (18/11/10pt "Segoe UI"); ``HEADING`` and ``CAPTION`` fill gaps the
#: current screens have no consistent equivalent for (see the UI audit's finding that
#: font usage today is ad hoc and screen-local).
TYPOGRAPHY: dict[str, TypeStyle] = {
    "display": TypeStyle(size=18, weight="bold"),
    "heading": TypeStyle(size=13, weight="bold"),
    "subheading": TypeStyle(size=11, weight="bold"),
    "body": TypeStyle(size=10, weight="normal"),
    "body_bold": TypeStyle(size=10, weight="bold"),
    "caption": TypeStyle(size=9, weight="normal"),
}

#: Base spacing unit in pixels. The current screens use ad hoc padx/pady values
#: (2, 4, 5, 6, 7, 8, 10, 12, 14 all appear); this scale replaces that with a single
#: 4px grid so future screens compose consistent spacing instead of inventing values.
SPACING_UNIT_PX = 4

#: Named multiples of ``SPACING_UNIT_PX``. Use ``spacing("sm")`` etc. rather than a
#: raw integer so the scale stays a single source of truth.
_SPACING_SCALE: dict[str, int] = {
    "xs": 1,
    "sm": 2,
    "md": 3,
    "lg": 4,
    "xl": 6,
}


def spacing(name: Literal["xs", "sm", "md", "lg", "xl"]) -> int:
    """Return the pixel value for a named point on the spacing scale."""

    return _SPACING_SCALE[name] * SPACING_UNIT_PX


StatusState = Literal["pass", "warning", "fail", "stale", "review_required", "info"]


class StatusStyle(BaseModel):
    """A semantic status rendering: color, symbol, and label are always paired.

    Never render ``color`` alone -- always pair it with ``symbol`` and/or ``label``
    text, per the #305 "never color-alone for state" requirement. ``ttk_style_name``
    is the style identifier ``configure_ttk_status_styles`` registers for this state.
    """

    model_config = ConfigDict(frozen=True)

    state: StatusState
    label: str
    symbol: str
    foreground: str
    slant: FontSlant = "roman"
    weight: FontWeight = "bold"

    @property
    def ttk_style_name(self) -> str:
        return f"Status.{self.state.title().replace('_', '')}.TLabel"

    def format(self, detail: str | None = None) -> str:
        """Compose the always-present symbol+label text for this status.

        This text is what actually carries the meaning; color is a reinforcing
        channel only. Callers can safely use the returned string even in contexts
        that cannot apply ttk styling at all (e.g. plain log/status text).
        """

        text = f"{self.symbol} {self.label}"
        return f"{text} — {detail}" if detail else text


#: Semantic status registry. Colors are chosen for readable contrast on the light
#: backgrounds ttk's default Windows themes ("vista"/"winnative") use; this slice does
#: not attempt dark-theme adaptation (out of scope -- see docs/ui/design-system-foundation.md).
STATUS_STYLES: dict[StatusState, StatusStyle] = {
    "pass": StatusStyle(
        state="pass",
        label="PASS",
        symbol="✓",  # check mark
        foreground="#1B5E20",
    ),
    "warning": StatusStyle(
        state="warning",
        label="WARNING",
        symbol="⚠",  # warning sign
        foreground="#8A5B00",
    ),
    "fail": StatusStyle(
        state="fail",
        label="FAIL",
        symbol="✗",  # ballot x
        foreground="#B3261E",
    ),
    "stale": StatusStyle(
        state="stale",
        label="STALE",
        symbol="⏳",  # hourglass
        foreground="#5C5C5C",
        slant="italic",
    ),
    "review_required": StatusStyle(
        state="review_required",
        label="REVIEW REQUIRED",
        symbol="◉",  # fisheye
        foreground="#3F51B5",
    ),
    "info": StatusStyle(
        state="info",
        label="INFO",
        symbol="ℹ",  # information source
        foreground="#37474F",
        weight="normal",
    ),
}


def status_style(state: StatusState) -> StatusStyle:
    """Look up the semantic status style for ``state``."""

    return STATUS_STYLES[state]


def format_status(state: StatusState, detail: str | None = None) -> str:
    """Convenience wrapper: ``format_status("fail", "97 unmapped notes")``."""

    return status_style(state).format(detail)


def configure_ttk_status_styles(style: object) -> None:
    """Register every semantic status as a named ``ttk.Style`` for ``TLabel`` widgets.

    Takes a live ``ttk.Style`` instance (typed as ``object`` here so importing this
    module never requires ``tkinter`` to be installed/importable -- see the
    module-level docstring and the project's pure-status-module convention used by
    e.g. ``validation_dashboard.py``). Callers pass a real ``ttk.Style(root)``; this
    function only calls ``.configure(name, **options)`` on it, which is exactly what
    ``ttk.Style`` exposes.
    """

    for status in STATUS_STYLES.values():
        font = TypeStyle(
            size=TYPOGRAPHY["body"].size,
            weight=status.weight,
            slant=status.slant,
        )
        style.configure(  # type: ignore[attr-defined]
            status.ttk_style_name,
            foreground=status.foreground,
            font=font.as_tuple(),
        )
