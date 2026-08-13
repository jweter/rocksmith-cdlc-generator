from __future__ import annotations

from pathlib import Path

import yaml

from rocksmith_cdlc_generator.benchmark_source_research import BenchmarkSourceResearchRecord


def test_committed_structured_reference_research_manifest_is_valid() -> None:
    payload = yaml.safe_load(
        Path("benchmarks/structured_reference_research.yaml").read_text(encoding="utf-8")
    )

    assert payload["schema_version"] == 1
    records = [BenchmarkSourceResearchRecord.model_validate(item) for item in payload["records"]]

    assert [record.benchmark_id for record in records] == ["BMARK-001", "BMARK-002"]
    assert all(record.finding == "other_structured_notation" for record in records)
    assert "MN0056221" in records[0].source_title
    assert "Songsterr" in records[1].source_title


def test_committed_research_manifest_has_unique_benchmark_ids() -> None:
    payload = yaml.safe_load(
        Path("benchmarks/structured_reference_research.yaml").read_text(encoding="utf-8")
    )
    records = [BenchmarkSourceResearchRecord.model_validate(item) for item in payload["records"]]
    benchmark_ids = [record.benchmark_id for record in records]

    assert len(benchmark_ids) == len(set(benchmark_ids))
