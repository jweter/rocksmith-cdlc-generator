from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rocksmith_cdlc_generator.candidate_bank_validation import (
    CandidateBankValidationError,
    validate_candidate_bank,
)


def _write_bank(tmp_path: Path, candidates: list[dict], schema_version: int = 1) -> Path:
    path = tmp_path / "candidate_bank.yaml"
    payload = {
        "schema_version": schema_version,
        "purpose": "test benchmark candidates",
        "promotion_policy": {"reference_rule": "human_review_required"},
        "candidates": candidates,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _candidate(rank: int = 1, benchmark_id: str = "BMARK-001") -> dict:
    return {
        "rank": rank,
        "benchmark_id": benchmark_id,
        "artist": "Example Artist",
        "title": "Example Song",
        "duration_seconds": 180.0,
        "tier": "tier_1_mvp",
        "role": "primary_reference",
        "structured_reference": {"status": "verified_good", "kind": "guitar_pro"},
        "dlc_library": {"status": "requires_full_cfsm_check"},
        "rationale": "Useful deterministic fixture.",
    }


def test_repository_candidate_bank_is_valid() -> None:
    bank = validate_candidate_bank(Path("benchmarks/candidate_bank.yaml"))
    assert bank.schema_version == 1
    assert len(bank.candidates) == 20
    assert bank.candidates[0].benchmark_id == "BMARK-001"


def test_rejects_unknown_schema_version(tmp_path: Path) -> None:
    path = _write_bank(tmp_path, [_candidate()], schema_version=2)
    with pytest.raises(CandidateBankValidationError, match="schema_version"):
        validate_candidate_bank(path)


def test_rejects_duplicate_rank_and_id(tmp_path: Path) -> None:
    first = _candidate()
    second = _candidate()
    path = _write_bank(tmp_path, [first, second])
    with pytest.raises(CandidateBankValidationError, match="ranks must be unique"):
        validate_candidate_bank(path)

    second = _candidate(rank=2)
    path = _write_bank(tmp_path, [first, second])
    with pytest.raises(CandidateBankValidationError, match="benchmark_id values must be unique"):
        validate_candidate_bank(path)


def test_rejects_non_contiguous_rank(tmp_path: Path) -> None:
    path = _write_bank(tmp_path, [_candidate(rank=2)])
    with pytest.raises(CandidateBankValidationError, match="contiguous"):
        validate_candidate_bank(path)


def test_rejects_invalid_enums_and_duration(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["tier"] = "tier_99"
    path = _write_bank(tmp_path, [candidate])
    with pytest.raises(CandidateBankValidationError, match="tier"):
        validate_candidate_bank(path)

    candidate = _candidate()
    candidate["structured_reference"]["status"] = "trusted_without_review"
    path = _write_bank(tmp_path, [candidate])
    with pytest.raises(CandidateBankValidationError, match="structured_reference"):
        validate_candidate_bank(path)

    candidate = _candidate()
    candidate["duration_seconds"] = 0
    path = _write_bank(tmp_path, [candidate])
    with pytest.raises(CandidateBankValidationError, match="duration_seconds"):
        validate_candidate_bank(path)


def test_rejects_non_finite_duration(tmp_path: Path) -> None:
    for duration in (float("inf"), float("-inf"), float("nan")):
        candidate = _candidate()
        candidate["duration_seconds"] = duration
        path = _write_bank(tmp_path, [candidate])
        with pytest.raises(CandidateBankValidationError, match="duration_seconds"):
            validate_candidate_bank(path)


def test_rejects_missing_required_metadata(tmp_path: Path) -> None:
    candidate = _candidate()
    del candidate["rationale"]
    path = _write_bank(tmp_path, [candidate])
    with pytest.raises(CandidateBankValidationError, match="rationale"):
        validate_candidate_bank(path)


def test_rejects_whitespace_only_required_candidate_metadata(tmp_path: Path) -> None:
    for field in ("artist", "title", "role", "rationale"):
        candidate = _candidate()
        candidate[field] = "   \t"
        path = _write_bank(tmp_path, [candidate])
        with pytest.raises(CandidateBankValidationError, match=field):
            validate_candidate_bank(path)

    candidate = _candidate()
    candidate["structured_reference"]["kind"] = "   "
    path = _write_bank(tmp_path, [candidate])
    with pytest.raises(CandidateBankValidationError, match="kind"):
        validate_candidate_bank(path)


def test_required_candidate_metadata_is_trimmed_canonically(tmp_path: Path) -> None:
    candidate = _candidate(benchmark_id="  BMARK-001  ")
    candidate["artist"] = "  Example Artist  "
    candidate["title"] = "  Example Song  "
    candidate["role"] = "  primary_reference  "
    candidate["rationale"] = "  Useful deterministic fixture.  "
    candidate["structured_reference"]["kind"] = "  guitar_pro  "
    path = _write_bank(tmp_path, [candidate])

    bank = validate_candidate_bank(path)

    assert bank.candidates[0].benchmark_id == "BMARK-001"
    assert bank.candidates[0].artist == "Example Artist"
    assert bank.candidates[0].title == "Example Song"
    assert bank.candidates[0].role == "primary_reference"
    assert bank.candidates[0].rationale == "Useful deterministic fixture."
    assert bank.candidates[0].structured_reference.kind == "guitar_pro"


@pytest.mark.parametrize(
    "field_name",
    ("local_audio_path", "source-file", "tab_filename", "reference_asset"),
)
def test_rejects_candidate_asset_location_fields(tmp_path: Path, field_name: str) -> None:
    candidate = _candidate()
    candidate[field_name] = "synthetic-location-sentinel"
    path = _write_bank(tmp_path, [candidate])

    with pytest.raises(CandidateBankValidationError, match="asset location fields"):
        validate_candidate_bank(path)


def test_rejects_nested_candidate_asset_location_fields(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["structured_reference"]["private_metadata"] = {
        "source_file": "synthetic-location-sentinel"
    }
    path = _write_bank(tmp_path, [candidate])

    with pytest.raises(CandidateBankValidationError, match=r"structured_reference\.private_metadata\.source_file"):
        validate_candidate_bank(path)


def test_allows_non_location_provenance_prose(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["structured_reference"]["notes"] = (
        "Reference material stays outside Git; human acceptance is still required."
    )
    candidate["dlc_library"]["notes"] = "No location metadata is recorded here."
    path = _write_bank(tmp_path, [candidate])

    bank = validate_candidate_bank(path)

    assert bank.candidates[0].structured_reference.notes is not None
