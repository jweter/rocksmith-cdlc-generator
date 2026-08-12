from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.benchmark_candidates import (
    BenchmarkCandidateValidationError,
    validate_candidate_bank,
    validate_candidate_bank_data,
)


def _candidate() -> dict:
    return {
        "rank": 1,
        "benchmark_id": "BMARK-001",
        "artist": "Example Artist",
        "title": "Example Song",
        "duration_seconds": 180.0,
        "tier": "tier_1_mvp",
        "role": "primary_reference",
        "structured_reference": {
            "status": "verified_good",
            "kind": "guitar_pro",
        },
        "dlc_library": {"status": "requires_full_cfsm_check"},
        "rationale": "Useful deterministic fixture.",
    }


def _bank() -> dict:
    return {
        "schema_version": 1,
        "purpose": "Benchmark metadata only.",
        "promotion_policy": {},
        "candidates": [_candidate()],
    }


def test_committed_candidate_bank_passes_validation() -> None:
    result = validate_candidate_bank(Path("benchmarks/candidate_bank.yaml"))

    assert result.candidate_count == 20
    assert result.ranks == tuple(range(1, 21))
    assert result.benchmark_ids[0] == "BMARK-001"
    assert result.benchmark_ids[-1] == "BMARK-020"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "schema_version"),
        ("purpose", "", "purpose"),
        ("promotion_policy", None, "promotion_policy"),
    ],
)
def test_rejects_invalid_root_contract(field: str, value: object, message: str) -> None:
    payload = _bank()
    payload[field] = value

    with pytest.raises(BenchmarkCandidateValidationError, match=message):
        validate_candidate_bank_data(payload)


def test_rejects_missing_required_candidate_metadata() -> None:
    payload = _bank()
    del payload["candidates"][0]["artist"]

    with pytest.raises(BenchmarkCandidateValidationError, match="missing required fields: artist"):
        validate_candidate_bank_data(payload)


def test_rejects_duplicate_rank_and_benchmark_id() -> None:
    duplicate = deepcopy(_candidate())
    duplicate["title"] = "Another Song"

    payload = _bank()
    payload["candidates"].append(duplicate)
    with pytest.raises(BenchmarkCandidateValidationError, match="ranks must be unique"):
        validate_candidate_bank_data(payload)

    duplicate["rank"] = 2
    with pytest.raises(BenchmarkCandidateValidationError, match="benchmark_id values must be unique"):
        validate_candidate_bank_data(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("tier", "unknown"), "tier is not an allowed value"),
        (("duration_seconds", 0), "duration_seconds must be finite and positive"),
        (("duration_seconds", float("nan")), "duration_seconds must be finite and positive"),
        (("duration_seconds", float("inf")), "duration_seconds must be finite and positive"),
        (("duration_seconds", float("-inf")), "duration_seconds must be finite and positive"),
    ],
)
def test_rejects_invalid_candidate_values(mutation: tuple[str, object], message: str) -> None:
    payload = _bank()
    key, value = mutation
    payload["candidates"][0][key] = value

    with pytest.raises(BenchmarkCandidateValidationError, match=message):
        validate_candidate_bank_data(payload)


def test_rejects_invalid_status_enums() -> None:
    payload = _bank()
    payload["candidates"][0]["structured_reference"]["status"] = "trusted"
    with pytest.raises(BenchmarkCandidateValidationError, match="structured_reference.status"):
        validate_candidate_bank_data(payload)

    payload = _bank()
    payload["candidates"][0]["dlc_library"]["status"] = "installed"
    with pytest.raises(BenchmarkCandidateValidationError, match="dlc_library.status"):
        validate_candidate_bank_data(payload)


@pytest.mark.parametrize(
    "unsafe_value",
    [
        r"C:\\Users\\example\\Music\\song.flac",
        "/home/example/song.wav",
        "file:///tmp/song.ogg",
        "Local source: file:///home/user/reference.json",
        "private/reference.psarc",
        "tabs/song.gp5",
    ],
)
def test_rejects_local_or_commercial_asset_paths(unsafe_value: str) -> None:
    payload = _bank()
    payload["candidates"][0]["structured_reference"]["notes"] = unsafe_value

    with pytest.raises(BenchmarkCandidateValidationError, match="not allowed"):
        validate_candidate_bank_data(payload)


def test_metadata_descriptions_do_not_become_ground_truth_or_path_false_positives() -> None:
    payload = _bank()
    payload["candidates"][0]["structured_reference"]["notes"] = (
        "Guitar Pro material identified during research; keep the actual source private."
    )

    result = validate_candidate_bank_data(payload)

    assert result.candidate_count == 1
