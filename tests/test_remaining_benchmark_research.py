import yaml

from rocksmith_cdlc_generator.benchmark_source_research import BenchmarkSourceResearchRecord


def test_remaining_benchmark_research_batch() -> None:
    with open("benchmarks/structured_reference_research/BMARK-004-020.yaml", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    records = [BenchmarkSourceResearchRecord.model_validate(item) for item in payload["records"]]
    assert len(records) == 17
    assert records[0].benchmark_id == "BMARK-004"
    assert records[-1].benchmark_id == "BMARK-020"
    assert len({record.benchmark_id for record in records}) == 17
