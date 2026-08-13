from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.benchmark_provenance import BenchmarkSourceProvenance


BASE = {
    "benchmark_id": "BMARK-001",
    "source_label": "synthetic reference candidate",
    "source_kind": "guitar_pro",
    "acquisition_license_note": "Synthetic test metadata only; no source bytes are committed.",
    "redistribution_status": "local_only",
    "sha256": "a" * 64,
}


def test_unaccepted_source_keeps_human_fields_empty() -> None:
    record = BenchmarkSourceProvenance(**BASE)

    assert record.accepted_by_human is False
    assert record.accepted_by is None
    assert record.acceptance_date is None


def test_human_acceptance_requires_reviewer_and_date() -> None:
    with pytest.raises(ValidationError, match="accepted_by"):
        BenchmarkSourceProvenance(**BASE, accepted_by_human=True)

    with pytest.raises(ValidationError, match="acceptance_date"):
        BenchmarkSourceProvenance(
            **BASE,
            accepted_by_human=True,
            accepted_by="human-reviewer",
        )

    record = BenchmarkSourceProvenance(
        **BASE,
        accepted_by_human=True,
        accepted_by="human-reviewer",
        acceptance_date=date(2026, 8, 12),
        known_limitations=("Technique markings need manual verification.",),
    )
    assert record.accepted_by_human is True


def test_unaccepted_record_rejects_premature_acceptance_metadata() -> None:
    with pytest.raises(ValidationError, match="must remain unset"):
        BenchmarkSourceProvenance(
            **BASE,
            accepted_by="human-reviewer",
            acceptance_date=date(2026, 8, 12),
        )


def test_record_requires_strict_benchmark_id_and_sha256() -> None:
    with pytest.raises(ValidationError):
        BenchmarkSourceProvenance(**{**BASE, "benchmark_id": "benchmark-1"})

    with pytest.raises(ValidationError):
        BenchmarkSourceProvenance(**{**BASE, "sha256": "not-a-hash"})


def test_record_forbids_source_paths_and_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="source_path"):
        BenchmarkSourceProvenance(
            **BASE,
            source_path=r"C:\\private\\copyrighted.gp5",
        )


def test_record_is_frozen_after_validation() -> None:
    record = BenchmarkSourceProvenance(**BASE)

    with pytest.raises(ValidationError):
        record.accepted_by_human = True
