from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

# Every RS2014 song-XML container element below is written by rocksmith_xml.py with a
# ``count`` attribute; this is the canonical set of direct children the <song> root itself
# must carry exactly once each (build_rocksmith_bass_xml/build_rocksmith_guitar_xml always
# emit every one of these, regardless of arrangement).
REQUIRED_SONG_CHILD_TAGS = (
    "title",
    "arrangement",
    "part",
    "offset",
    "centOffset",
    "songLength",
    "startBeat",
    "averageTempo",
    "tuning",
    "capo",
    "artistName",
    "artistNameSort",
    "albumName",
    "albumYear",
    "crowdSpeed",
    "arrangementProperties",
    "phrases",
    "phraseIterations",
    "newLinkedDiffs",
    "linkedDiffs",
    "phraseProperties",
    "ebeats",
    "sections",
    "events",
    "transcriptionTrack",
    "chordTemplates",
    "fretHandMuteTemplates",
    "levels",
)


@dataclass(frozen=True)
class StructuralFinding:
    path: str
    message: str


def _element_path(ancestry: list[str], tag: str) -> str:
    return "/".join((*ancestry, tag))


def _check_counts(
    element: ET.Element, ancestry: list[str], findings: list[StructuralFinding]
) -> None:
    declared = element.get("count")
    if declared is not None:
        actual = len(list(element))
        try:
            declared_int = int(declared)
        except ValueError:
            findings.append(
                StructuralFinding(
                    path=_element_path(ancestry, element.tag),
                    message=f"count attribute {declared!r} is not an integer",
                )
            )
        else:
            if declared_int != actual:
                findings.append(
                    StructuralFinding(
                        path=_element_path(ancestry, element.tag),
                        message=f"count={declared_int} does not match {actual} child element(s)",
                    )
                )
    child_ancestry = [*ancestry, element.tag]
    for child in element:
        _check_counts(child, child_ancestry, findings)


def _check_required_song_children(
    root: ET.Element, findings: list[StructuralFinding]
) -> None:
    if root.tag != "song":
        findings.append(StructuralFinding(path=root.tag, message="root element is not <song>"))
        return
    tags_present = [child.tag for child in root]
    for required_tag in REQUIRED_SONG_CHILD_TAGS:
        occurrences = tags_present.count(required_tag)
        if occurrences != 1:
            findings.append(
                StructuralFinding(
                    path=f"song/{required_tag}",
                    message=f"expected exactly one <{required_tag}>, found {occurrences}",
                )
            )


def structural_findings(root: ET.Element) -> list[StructuralFinding]:
    """Return every structural self-consistency defect found in a built Rocksmith XML tree.

    Every RS2014 authoring XML container element declares a ``count`` attribute that must
    equal its actual number of direct children; a mismatch produces a corrupt/unplayable
    file that Rocksmith, DDC, or the DLC Builder can reject or silently truncate. This
    proves the concrete in-memory ``ElementTree`` this project is about to write is
    internally consistent, independent of and in addition to the upstream semantic
    validation in ``playability_validation.py``/``guitar_validation.py``, which run before
    the tree is even built.
    """

    findings: list[StructuralFinding] = []
    _check_counts(root, [], findings)
    _check_required_song_children(root, findings)
    return findings


class RocksmithXmlStructuralError(ValueError):
    """Raised when a built Rocksmith XML tree fails structural self-consistency checks."""

    def __init__(self, findings: list[StructuralFinding]) -> None:
        self.findings = findings
        detail = "; ".join(f"{finding.path}: {finding.message}" for finding in findings)
        super().__init__(f"Rocksmith XML structural validation failed: {detail}")


def require_structurally_valid(root: ET.Element) -> None:
    """Raise ``RocksmithXmlStructuralError`` if ``root`` fails structural self-consistency."""

    findings = structural_findings(root)
    if findings:
        raise RocksmithXmlStructuralError(findings)
