from pathlib import Path

from rocksmith_cdlc_generator.benchmark_source_research import (
    load_benchmark_source_research_manifest,
)


def test_canonical_research_manifest_resolves_all_twenty_candidates() -> None:
    records = load_benchmark_source_research_manifest(
        Path("benchmarks/structured_reference_research.yaml")
    )

    assert [record.benchmark_id for record in records] == [
        f"BMARK-{index:03d}" for index in range(1, 21)
    ]
    assert all(record.finding == "other_structured_notation" for record in records)
    assert all(record.source_page_url is not None for record in records)
