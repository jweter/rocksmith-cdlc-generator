from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.benchmark_promotion import BenchmarkPromotionRecord


def _ready_record(**overrides: object) -> BenchmarkPromotionRecord:
    payload = {
        "benchmark_id": "BMARK-001",
        "library_absence_verified": True,
        "lawful_local_audio_available": True,
        "reference_source_available": True,
        "reference_accepted_by_human": True,
        "excerpt_start_seconds": 60.0,
        "excerpt_end_seconds": 120.0,
        "provenance_recorded": True,
    }
    payload.update(overrides)
    return BenchmarkPromotionRecord.model_validate(payload)


def test_ready_record_passes_only_when_every_gate_is_satisfied() -> None:
    record = _ready_record()
    assert record.ready_for_trusted_benchmark is True
    assert record.blocking_reasons == ()


def test_each_required_gate_blocks_promotion() -> None:
    fields = {
        "library_absence_verified": "library_absence_not_verified",
        "lawful_local_audio_available": "lawful_local_audio_not_available",
        "reference_source_available": "reference_source_not_available",
        "reference_accepted_by_human": "reference_not_accepted_by_human",
        "provenance_recorded": "provenance_not_recorded",
    }
    for field, reason in fields.items():
        record = _ready_record(**{field: False})
        assert record.ready_for_trusted_benchmark is False
        assert reason in record.blocking_reasons


def test_excerpt_must_be_selected_as_a_pair() -> None:
    with pytest.raises(ValueError, match="provided together"):
        _ready_record(excerpt_end_seconds=None)


def test_excerpt_duration_must_be_30_to_90_seconds() -> None:
    for end in (89.9, 150.1):
        with pytest.raises(ValueError, match="30 to 90"):
            _ready_record(excerpt_start_seconds=60.0, excerpt_end_seconds=end)


def test_human_acceptance_cannot_be_replaced_by_source_availability() -> None:
    record = _ready_record(reference_accepted_by_human=False)
    assert record.reference_source_available is True
    assert record.ready_for_trusted_benchmark is False
    assert "reference_not_accepted_by_human" in record.blocking_reasons


def test_model_forbids_untracked_extra_fields() -> None:
    with pytest.raises(ValueError):
        BenchmarkPromotionRecord.model_validate({
            "benchmark_id": "BMARK-001",
            "source_path": "not-allowed",
        })
