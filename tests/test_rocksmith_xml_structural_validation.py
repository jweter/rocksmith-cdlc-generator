from xml.etree import ElementTree as ET

import pytest

from rocksmith_cdlc_generator.rocksmith_xml_structural_validation import (
    RocksmithXmlStructuralError,
    StructuralFinding,
    require_structurally_valid,
    structural_findings,
)


def _minimal_valid_song() -> ET.Element:
    root = ET.Element("song", {"version": "7"})
    for tag in (
        "title",
        "arrangement",
        "part",
        "offset",
        "centOffset",
        "songLength",
        "startBeat",
        "averageTempo",
        "capo",
        "artistName",
        "artistNameSort",
        "albumName",
        "albumYear",
        "crowdSpeed",
    ):
        ET.SubElement(root, tag).text = "0"
    ET.SubElement(root, "tuning")
    ET.SubElement(root, "arrangementProperties")

    phrases = ET.SubElement(root, "phrases", {"count": "1"})
    ET.SubElement(phrases, "phrase")

    phrase_iterations = ET.SubElement(root, "phraseIterations", {"count": "1"})
    ET.SubElement(phrase_iterations, "phraseIteration")

    ET.SubElement(root, "newLinkedDiffs", {"count": "0"})
    ET.SubElement(root, "linkedDiffs", {"count": "0"})
    ET.SubElement(root, "phraseProperties", {"count": "0"})

    ebeats = ET.SubElement(root, "ebeats", {"count": "1"})
    ET.SubElement(ebeats, "ebeat")

    sections = ET.SubElement(root, "sections", {"count": "1"})
    ET.SubElement(sections, "section")

    events = ET.SubElement(root, "events", {"count": "1"})
    ET.SubElement(events, "event")

    ET.SubElement(root, "transcriptionTrack", {"difficulty": "-1"})
    ET.SubElement(root, "chordTemplates", {"count": "0"})
    ET.SubElement(root, "fretHandMuteTemplates", {"count": "0"})

    levels = ET.SubElement(root, "levels", {"count": "1"})
    ET.SubElement(levels, "level")

    return root


def test_minimal_valid_song_has_no_findings() -> None:
    assert structural_findings(_minimal_valid_song()) == []
    require_structurally_valid(_minimal_valid_song())  # does not raise


def test_count_mismatch_is_reported_with_element_path() -> None:
    root = _minimal_valid_song()
    root.find("ebeats").set("count", "2")

    findings = structural_findings(root)

    assert len(findings) == 1
    assert findings[0].path == "song/ebeats"
    assert "count=2 does not match 1 child element(s)" in findings[0].message


def test_nested_count_mismatch_reports_full_path() -> None:
    root = _minimal_valid_song()
    root.find("levels/level").set("count", "3")

    findings = structural_findings(root)

    assert findings[0].path == "song/levels/level"


def test_non_integer_count_attribute_is_reported() -> None:
    root = _minimal_valid_song()
    root.find("ebeats").set("count", "not-a-number")

    findings = structural_findings(root)

    assert len(findings) == 1
    assert findings[0].path == "song/ebeats"
    assert "not an integer" in findings[0].message


def test_missing_required_song_child_is_reported() -> None:
    root = _minimal_valid_song()
    root.remove(root.find("capo"))

    findings = structural_findings(root)

    assert any(finding.path == "song/capo" for finding in findings)


def test_duplicate_required_song_child_is_reported() -> None:
    root = _minimal_valid_song()
    ET.SubElement(root, "capo").text = "0"

    findings = structural_findings(root)

    assert any(
        finding.path == "song/capo" and "found 2" in finding.message for finding in findings
    )


def test_non_song_root_is_reported() -> None:
    root = ET.Element("notASong")

    findings = structural_findings(root)

    assert findings == [StructuralFinding(path="notASong", message="root element is not <song>")]


def test_require_structurally_valid_raises_with_findings_attached() -> None:
    root = _minimal_valid_song()
    root.find("ebeats").set("count", "9")

    with pytest.raises(RocksmithXmlStructuralError) as excinfo:
        require_structurally_valid(root)

    assert excinfo.value.findings[0].path == "song/ebeats"
    assert "song/ebeats" in str(excinfo.value)
