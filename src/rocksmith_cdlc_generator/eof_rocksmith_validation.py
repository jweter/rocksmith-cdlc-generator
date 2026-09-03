from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

Severity = Literal["FAIL", "WARNING"]

# Current neutral note models preserve only the presence of these techniques,
# not the Rocksmith-specific detail required for lossless export. They receive
# specialized EOF-derived findings rather than a duplicate generic
# unsupported-technique warning.
SPECIALIZED_UNSUPPORTED_TECHNIQUES = frozenset({"bend", "slide"})


@dataclass(frozen=True)
class RocksmithRuleFinding:
    """A model-neutral Rocksmith authoring finding derived from EOF behavior."""

    code: str
    severity: Severity
    message: str
    priority: int
    time_seconds: float | None = None
    note_index: int | None = None


def note_rule_findings(
    *,
    fret: int,
    techniques: Sequence[str],
    label: str,
    time_seconds: float,
    note_index: int | None,
    check_fret_limit: bool = True,
    has_exportable_bend_curve: bool = False,
) -> list[RocksmithRuleFinding]:
    """Return EOF-derived rules supported by the current neutral note model.

    These rules intentionally diagnose only facts represented in project data.
    They never invent bend strengths, slide targets, link-next state, fingering,
    or fret-hand positions. ``check_fret_limit`` lets callers that already own a
    stricter configured fret gate avoid duplicate failures while still reusing the
    EOF-derived technique checks. ``has_exportable_bend_curve`` should be true only
    when the note's bend has real per-point curve data (see
    ``rocksmith_xml.note_has_exportable_bend_curve``); it suppresses the
    ``rocksmith_bend_detail_missing`` finding once that data is actually exported
    losslessly instead of merely being present as a technique label.
    """

    findings: list[RocksmithRuleFinding] = []
    technique_set = set(techniques)

    if check_fret_limit and fret > 24:
        findings.append(
            RocksmithRuleFinding(
                code="rocksmith_fret_limit_exceeded",
                severity="FAIL",
                message=(
                    f"{label} uses fret {fret}; Rocksmith 2014 supports playable "
                    "notes only through fret 24."
                ),
                priority=100,
                time_seconds=time_seconds,
                note_index=note_index,
            )
        )

    if "bend" in technique_set:
        if fret == 0:
            findings.append(
                RocksmithRuleFinding(
                    code="rocksmith_open_string_bend",
                    severity="WARNING",
                    message=(
                        f"{label} is an open-string bend. EOF flags open-note bends "
                        "for Rocksmith author review."
                    ),
                    priority=88,
                    time_seconds=time_seconds,
                    note_index=note_index,
                )
            )
        if not has_exportable_bend_curve:
            findings.append(
                RocksmithRuleFinding(
                    code="rocksmith_bend_detail_missing",
                    severity="WARNING",
                    message=(
                        f"{label} contains a bend, but the current neutral model preserves "
                        "only bend presence, not bend strength/curve points; lossless "
                        "Rocksmith export requires review."
                    ),
                    priority=86,
                    time_seconds=time_seconds,
                    note_index=note_index,
                )
            )

    if "slide" in technique_set:
        findings.append(
            RocksmithRuleFinding(
                code="rocksmith_slide_detail_missing",
                severity="WARNING",
                message=(
                    f"{label} contains a slide, but the current neutral model does not "
                    "preserve the Rocksmith slide end fret/direction/link-next detail; "
                    "lossless export requires review."
                ),
                priority=86,
                time_seconds=time_seconds,
                note_index=note_index,
            )
        )

    return findings


def guitar_chart_rule_findings(
    *,
    chord_count: int,
    playable_event_count: int,
) -> list[RocksmithRuleFinding]:
    """Return EOF-derived chart-level warnings supported by current export state."""

    findings: list[RocksmithRuleFinding] = []
    if playable_event_count <= 0:
        return findings

    if chord_count > 0:
        findings.append(
            RocksmithRuleFinding(
                code="rocksmith_chord_fingering_missing",
                severity="WARNING",
                message=(
                    f"Chart contains {chord_count} chord event(s), but chord fingering "
                    "is not yet modeled/exported. EOF treats missing chord fingering as "
                    "an authoring warning."
                ),
                priority=84,
            )
        )

    findings.append(
        RocksmithRuleFinding(
            code="rocksmith_fhp_missing",
            severity="WARNING",
            message=(
                "Chart contains playable guitar events, but fret-hand-position anchors "
                "are not yet modeled/exported. EOF treats missing FHPs as an authoring "
                "warning."
            ),
            priority=82,
        )
    )
    return findings


def generic_unsupported_techniques(techniques: Iterable[str]) -> tuple[str, ...]:
    """Remove techniques that receive a more actionable specialized finding."""

    return tuple(
        technique
        for technique in techniques
        if technique not in SPECIALIZED_UNSUPPORTED_TECHNIQUES
    )
