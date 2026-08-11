import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.local_psarc_workspace import copy_psarc_for_inspection
from rocksmith_cdlc_generator.local_tone_indexer import (
    merge_private_extraction,
    parse_private_extraction,
)
from rocksmith_cdlc_generator.private_psarc_extraction import PrivatePsarcExtraction


def _manifest() -> dict:
    return {
        "Entries": {
            "song": {
                "arrangement": {
                    "ArtistName": "Synthetic Artist",
                    "SongName": "Synthetic Song",
                    "ArrangementName": "Lead",
                    "ArrangementProperties": {"PathLead": 1, "PathRhythm": 0, "PathBass": 0},
                    "Tones": [
                        {
                            "Key": "tone-a",
                            "Name": "Synthetic Lead",
                            "ToneDescriptors": ["distortion", "delay"],
                            "GearList": {
                                "Amp": {"Key": "amp-a", "KnobValues": {"Gain": 0.7}},
                                "Rack1": {"Key": "delay-a", "KnobValues": {"Time": 0.4}},
                            },
                        }
                    ],
                }
            }
        }
    }


def _setup(tmp_path: Path):
    rocksmith = tmp_path / "Rocksmith2014"
    dlc = rocksmith / "dlc"
    dlc.mkdir(parents=True)
    source = dlc / "synthetic_p.psarc"
    source.write_bytes(b"synthetic-psarc")
    workspace = tmp_path / "private-workspace"
    verified = copy_psarc_for_inspection(source, workspace_root=workspace, rocksmith_root=rocksmith)
    extracted = workspace / "extracted" / verified.source_sha256
    extracted.mkdir(parents=True, exist_ok=True)
    manifest = extracted / "manifest.json"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    receipt = PrivatePsarcExtraction(
        source_sha256=verified.source_sha256,
        verified_copy=str(verified.copy.resolve()),
        extracted_directory=str(extracted.resolve()),
        entry_count=1,
        json_files=[str(manifest.resolve())],
        sng_files=[],
        tone_json_candidates=[str(manifest.resolve())],
    )
    return rocksmith, dlc, source, workspace, verified, receipt


def test_parses_only_from_matching_verified_extraction(tmp_path: Path) -> None:
    _, _, source, _, verified, receipt = _setup(tmp_path)
    tones = parse_private_extraction(receipt, verified=verified, source_type="official_rocksmith")
    assert len(tones) == 1
    assert tones[0].source_path == str(source.resolve())
    assert tones[0].source_type == "official_rocksmith"
    assert tones[0].tone_key == "tone-a"


def test_rejects_receipt_hash_mismatch(tmp_path: Path) -> None:
    _, _, _, _, verified, receipt = _setup(tmp_path)
    bad = receipt.model_copy(update={"source_sha256": "f" * 64})
    with pytest.raises(ValueError, match="SHA-256"):
        parse_private_extraction(bad, verified=verified, source_type="official_rocksmith")


def test_rejects_candidate_outside_private_extraction(tmp_path: Path) -> None:
    _, _, _, _, verified, receipt = _setup(tmp_path)
    escaped = tmp_path / "escaped.json"
    escaped.write_text(json.dumps(_manifest()), encoding="utf-8")
    bad = receipt.model_copy(update={"tone_json_candidates": [str(escaped)]})
    with pytest.raises(ValueError, match="escaped"):
        parse_private_extraction(bad, verified=verified, source_type="official_rocksmith")


def test_merge_records_installed_source_not_private_copy(tmp_path: Path) -> None:
    _, dlc, source, _, verified, receipt = _setup(tmp_path)
    library = merge_private_extraction(
        receipt,
        verified=verified,
        source_type="official_rocksmith",
        dlc_root=dlc,
    )
    assert len(library.psarcs) == 1
    assert library.psarcs[0].path == str(source.resolve())
    assert library.psarcs[0].source_type == "official_rocksmith"
    assert len(library.tones) == 1
    assert library.tones[0].source_path == str(source.resolve())


def test_malformed_candidate_is_ignored_not_invented(tmp_path: Path) -> None:
    _, _, _, _, verified, receipt = _setup(tmp_path)
    malformed = Path(receipt.extracted_directory) / "bad.json"
    malformed.write_text("{not-json", encoding="utf-8")
    changed = receipt.model_copy(update={"tone_json_candidates": [str(malformed.resolve())]})
    assert parse_private_extraction(changed, verified=verified, source_type="custom_dlc") == []
