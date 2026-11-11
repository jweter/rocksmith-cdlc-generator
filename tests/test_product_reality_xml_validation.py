from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from rocksmith_cdlc_generator.build_staging import BuildAsset, BuildStageManifest
from rocksmith_cdlc_generator.product_reality_xml_validation import (
    collect_xml_structural_validation_evidence,
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


def _write_xml(path: Path, root: ET.Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _asset(role: str, path: Path) -> BuildAsset:
    return BuildAsset(role=role, path=str(path), size_bytes=1, sha256="a" * 64)


def _write_manifest(project_dir: Path, assets: list[BuildAsset]) -> None:
    manifest = BuildStageManifest(
        package_generation="1",
        validation_status="PASS",
        dlcbuilder_project=str(project_dir / "build" / "dlcbuilder" / "song.rs2dlc"),
        dlcbuilder_project_sha256="b" * 64,
        assets=assets,
    )
    stage_dir = project_dir / "build" / "staging"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "build_readiness.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )


def test_no_staged_build_is_review_required_without_private_path(tmp_path: Path) -> None:
    project = tmp_path / "private-song-project"

    evidence = collect_xml_structural_validation_evidence(project)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.roles_checked == []
    assert str(project) not in evidence.message


def test_manifest_without_xml_assets_is_review_required(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [_asset("song_audio", tmp_path / "song.wav")],
    )

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"


def test_unreadable_manifest_is_review_required(tmp_path: Path) -> None:
    stage_dir = tmp_path / "build" / "staging"
    stage_dir.mkdir(parents=True)
    (stage_dir / "build_readiness.json").write_text("not json", encoding="utf-8")

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"


def test_structurally_valid_staged_xml_passes(tmp_path: Path) -> None:
    bass_xml = tmp_path / "build" / "dlcbuilder" / "bass.xml"
    _write_xml(bass_xml, _minimal_valid_song())
    _write_manifest(tmp_path, [_asset("bass_xml", bass_xml)])

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    assert evidence.status == "PASS"
    assert evidence.roles_checked == ["bass_xml"]
    assert evidence.findings == []


def test_structurally_inconsistent_staged_xml_fails_with_sanitized_findings(
    tmp_path: Path,
) -> None:
    root = _minimal_valid_song()
    root.find("phrases").set("count", "2")
    bass_xml = tmp_path / "build" / "dlcbuilder" / "bass.xml"
    _write_xml(bass_xml, root)
    _write_manifest(tmp_path, [_asset("bass_xml", bass_xml)])

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    assert evidence.status == "FAIL"
    assert [item.model_dump() for item in evidence.findings] == [
        {"role": "bass_xml", "finding_count": 1}
    ]
    assert str(tmp_path) not in evidence.message


def test_missing_staged_xml_file_fails_without_private_path(tmp_path: Path) -> None:
    bass_xml = tmp_path / "build" / "dlcbuilder" / "bass.xml"
    _write_manifest(tmp_path, [_asset("bass_xml", bass_xml)])

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    assert evidence.status == "FAIL"
    assert str(tmp_path) not in evidence.message


def test_malformed_staged_xml_fails_without_private_path(tmp_path: Path) -> None:
    bass_xml = tmp_path / "build" / "dlcbuilder" / "bass.xml"
    bass_xml.parent.mkdir(parents=True)
    bass_xml.write_text("<song><unclosed></song>", encoding="utf-8")
    _write_manifest(tmp_path, [_asset("bass_xml", bass_xml)])

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    assert evidence.status == "FAIL"
    assert str(tmp_path) not in evidence.message


def test_multiple_arrangement_roles_are_each_checked(tmp_path: Path) -> None:
    bass_xml = tmp_path / "build" / "dlcbuilder" / "bass.xml"
    lead_xml = tmp_path / "build" / "dlcbuilder" / "lead.xml"
    _write_xml(bass_xml, _minimal_valid_song())
    _write_xml(lead_xml, _minimal_valid_song())
    _write_manifest(
        tmp_path,
        [_asset("lead_xml", lead_xml), _asset("bass_xml", bass_xml)],
    )

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    assert evidence.status == "PASS"
    assert evidence.roles_checked == ["bass_xml", "lead_xml"]


def test_evidence_is_json_serializable(tmp_path: Path) -> None:
    bass_xml = tmp_path / "build" / "dlcbuilder" / "bass.xml"
    _write_xml(bass_xml, _minimal_valid_song())
    _write_manifest(tmp_path, [_asset("bass_xml", bass_xml)])

    evidence = collect_xml_structural_validation_evidence(tmp_path)

    json.loads(evidence.model_dump_json())
