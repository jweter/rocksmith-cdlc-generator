from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuidedNextActionPresentation:
    """Presentation-only treatment for the guided shell's single next action.

    This deliberately carries no workflow authority. The caller still decides which
    action is currently valid; this model only makes that already-authoritative action
    visually explicit for a first-time user, per issue #305.
    """

    eyebrow: str
    button_text: str
    button_style: str


def present_guided_next_action(label: str, *, needs_human: bool) -> GuidedNextActionPresentation:
    """Return a non-color-only, high-salience presentation for one valid action."""

    normalized = label.strip()
    if not normalized:
        raise ValueError("guided next-action label must not be empty")

    if needs_human:
        return GuidedNextActionPresentation(
            eyebrow="NEXT REQUIRED ACTION ›",
            button_text=f"› {normalized}",
            button_style="Primary.TButton",
        )

    return GuidedNextActionPresentation(
        eyebrow="NEXT ACTION ›",
        button_text=f"› {normalized}",
        button_style="Primary.TButton",
    )
