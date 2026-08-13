from pathlib import Path

import yaml

from rocksmith_cdlc_generator.benchmark_source_research import BenchmarkSourceResearchRecord


def test_bmark003_record() -> None:
    data = yaml.safe_load(Path("benchmarks/structured_reference_research/BMARK-003.yaml").read_text())
    record = BenchmarkSourceResearchRecord.model_validate(data)
    assert record.benchmark_id == "BMARK-003"
