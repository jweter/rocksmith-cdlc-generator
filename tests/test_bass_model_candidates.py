"""Metadata integrity and false-admission tests; no models, network or media."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from rocksmith_cdlc_generator.bass_model_candidates import (
    ModelCardError, load_candidate_catalog, public_research_comparison,
    validate_candidate_catalog,
)


def test_published_model_comparison_is_research_only():
    raw = load_candidate_catalog()
    cards = validate_candidate_catalog(raw)
    assert len(cards) == 5
    assert sum("bass" in c["source_stems"] for c in cards) == 4
    assert any(c["role"] == "NEGATIVE_CONTROL_NOT_BASS" for c in cards)
    assert all(c["approved_for_execution"] is False for c in cards)
    assert all(c["local_bundle_sha256_verified"] is False for c in cards)
    assert all(c["local_ram_peak_measured"] is False for c in cards)
    report = public_research_comparison(raw)
    assert report["status"] == "RESEARCH_ONLY_NO_EXECUTION"
    assert report["model_execution_authorized"] is False
    assert report["song_or_gameplay_validated"] is False
    assert report["not_bass_isolation"] == ["uvr_mdx_inst_hq3_mlx"]
    assert not any(x in json.dumps(report) for x in (".wav", ".psarc", "C:\\", "source_path"))


@pytest.mark.parametrize(("field", "value"), [
    ("approved_for_execution", True),
    ("local_bundle_sha256_verified", True),
    ("weights_license_independently_cleared", True),
    ("network_isolation_proven", True),
    ("local_ram_peak_measured", True),
    ("approved_for_execution", 1),
])
def test_unproven_permissions_never_allowed(field, value):
    payload = deepcopy(load_candidate_catalog())
    payload["candidate_cards"][0][field] = value
    with pytest.raises(ModelCardError, match="MODEL_CARD_UNPROVEN_PERMISSION"):
        validate_candidate_catalog(payload)


def test_vocals_instrumental_model_can_never_be_marked_bass_stem():
    payload = deepcopy(load_candidate_catalog())
    payload["candidate_cards"][-1]["role"] = "BASS_SOURCE_CANDIDATE"
    with pytest.raises(ModelCardError, match="INSTRUMENTAL_MIX_IS_NOT_BASS_STEM"):
        validate_candidate_catalog(payload)


@pytest.mark.parametrize("change", [
    lambda p: p["candidate_cards"].append(deepcopy(p["candidate_cards"][0])),
    lambda p: p["candidate_cards"][0].update(source_url="http://localhost"),
    lambda p: p["candidate_cards"][0].update(size_source_url="https://example.com/fake"),
    lambda p: p["candidate_cards"][0].update(published_artifact_size=0),
    lambda p: p["candidate_cards"][0].update(published_artifact_size=True),
    lambda p: p["candidate_cards"][0].update(runtime_context="WINDOWS_VERIFIED"),
    lambda p: p["candidate_cards"][0].update(weight_license_evidence="LICENSE_APPROVED"),
    lambda p: p["candidate_cards"][0].update(source_stems=[]),
    lambda p: p["candidate_cards"][0].update(artifact_format="EXECUTABLE_SCRIPT"),
    lambda p: p.update(purpose="READY_FOR_MODEL_EXECUTION"),
])
def test_corrupt_or_unlicensed_cards_fail_closed(change):
    payload = deepcopy(load_candidate_catalog())
    change(payload)
    with pytest.raises(ModelCardError):
        validate_candidate_catalog(payload)


def test_missing_source_or_private_path_is_refused():
    payload = deepcopy(load_candidate_catalog())
    del payload["candidate_cards"][0]["size_source_url"]
    with pytest.raises(ModelCardError, match="MODEL_CARD_FIELDS_INVALID"):
        validate_candidate_catalog(payload)
    payload = deepcopy(load_candidate_catalog())
    payload["candidate_cards"][0]["note"] = "C:\\Private\\Music\\secret.wav"
    with pytest.raises(ModelCardError, match="MODEL_CARD_NOTE_INVALID"):
        validate_candidate_catalog(payload)


def test_private_media_filename_in_card_note_is_refused():
    payload = deepcopy(load_candidate_catalog())
    payload["candidate_cards"][0]["note"] = "Private benchmark file secret.wav must never enter the public catalog"
    with pytest.raises(ModelCardError, match="MODEL_CARD_NOTE_INVALID"):
        validate_candidate_catalog(payload)
