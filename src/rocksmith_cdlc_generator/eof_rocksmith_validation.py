from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

Severity = Literal["FAIL", "WARNING"]

# Current neutral note models preserve only the presence of these techniques,
# not the Rocksmith-specific detail required for lossless export. They receive
# specialized EOF-derived findings rather than a duplicate generic
# unsupported-technique warning.
SPECIALIZED_UNSUPPORTED_TECHNIQUES = frozenset({"bend", "slide"})

# raynebc/editor-on-fire's src/menu/file.c (eof_check_tempo_range(40.0, 300.0), gated by the
# eof_rs_export_suppress_tempo_warning preference declared in src/main.c) asks the chart author
# to confirm before saving any Rocksmith-capable file containing a beat whose instantaneous
# tempo (60000000 / ppqn, src/beat.c's eof_check_tempo_range) falls outside 40-300 BPM.
# Rocksmith's own XML/SNG formats enforce no such bound; this is EOF's own editor-side sanity
# check against likely tempo-detection or authoring mistakes, not a hard Rocksmith import
# constraint, so it is modeled here as an advisory WARNING rather than a packaging-blocking
# FAIL (docs/eof-subsystem-parity-matrix.md's "Tempo warning thresholds" row, issue #414).
EOF_TEMPO_RANGE_MIN_BPM = 40.0
EOF_TEMPO_RANGE_MAX_BPM = 300.0


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
    has_exportable_slide_target: bool = False,
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
    ``has_exportable_slide_target`` is the same suppression for
    ``rocksmith_slide_detail_missing``, true only when the slide's destination fret was
    actually resolved (see ``rocksmith_xml.note_has_exportable_slide_target``).
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

    if "slide" in technique_set and not has_exportable_slide_target:
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
    chords_missing_fingering: int,
    playable_event_count: int,
) -> list[RocksmithRuleFinding]:
    """Return EOF-derived chart-level warnings supported by current export state.

    ``chords_missing_fingering`` counts only chords whose ``chordTemplate`` would
    actually export with every finger left undefined (see
    ``rocksmith_xml.chord_exports_without_fingering()``), not every chord in the
    chart -- a chord with complete source ``left_hand_finger`` data is modeled and
    exported losslessly and does not need this authoring warning (issue #414).
    """

    findings: list[RocksmithRuleFinding] = []
    if playable_event_count <= 0:
        return findings

    if chords_missing_fingering > 0:
        findings.append(
            RocksmithRuleFinding(
                code="rocksmith_chord_fingering_missing",
                severity="WARNING",
                message=(
                    f"Chart contains {chords_missing_fingering} chord event(s) whose "
                    "fingering could not be determined from source data, so they export "
                    "with undefined chordTemplate fingers. EOF treats missing chord "
                    "fingering as an authoring warning."
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


def tempo_range_rule_finding(
    *, bpm: float, beat_index: int, time_seconds: float
) -> RocksmithRuleFinding | None:
    """Flag a beat whose tempo falls outside EOF's advisory Rocksmith export range.

    Unlike EOF's own single early-exit save-time dialog (eof_check_tempo_range returns only
    the first offending beat position), callers report every offending beat so a reviewer can
    see the full extent of the issue at once; this is a presentation difference only, not a
    change to which beats are considered out of range.
    """

    if EOF_TEMPO_RANGE_MIN_BPM <= bpm <= EOF_TEMPO_RANGE_MAX_BPM:
        return None
    return RocksmithRuleFinding(
        code="rocksmith_tempo_out_of_range",
        severity="WARNING",
        message=(
            f"Beat {beat_index} tempo is {bpm:.1f} BPM, outside EOF's advisory "
            f"{EOF_TEMPO_RANGE_MIN_BPM:.0f}-{EOF_TEMPO_RANGE_MAX_BPM:.0f} BPM Rocksmith export "
            "range; please confirm this reflects the actual recording tempo."
        ),
        priority=70,
        time_seconds=time_seconds,
    )


def generic_unsupported_techniques(techniques: Iterable[str]) -> tuple[str, ...]:
    """Remove techniques that receive a more actionable specialized finding."""

    return tuple(
        technique
        for technique in techniques
        if technique not in SPECIALIZED_UNSUPPORTED_TECHNIQUES
    )
