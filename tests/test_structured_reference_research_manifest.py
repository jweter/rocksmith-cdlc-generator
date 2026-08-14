from __future__ import annotations

from pathlib import Path

import yaml

from rocksmith_cdlc_generator.benchmark_source_research import (
    BenchmarkSourceResearchRecord,
    load_benchmark_source_research_manifest,
)


MANIFEST = Path("benchmarks/structured_reference_research.yaml")
CANDIDATE_BANK = Path("benchmarks/candidate_bank.yaml")


def test_committed_structured_reference_research_manifest_is_valid() -> None:
    payload = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    records = [BenchmarkSourceResearchRecord.model_validate(item) for item in payload["records"]]

    assert [record.benchmark_id for record in records] == ["BMARK-001", "BMARK-002"]
    assert records[0].finding == "official_commercial_guitar_pro"
    assert "guitar-pro.com" in str(records[0].source_page_url)
    assert "mySongBook" in records[0].source_title
    assert records[1].finding == "other_structured_notation"
    assert "Songsterr" in records[1].source_title


def test_committed_research_manifest_matches_candidate_bank() -> None:
    records = load_benchmark_source_research_manifest(MANIFEST)
    research_ids = {record.benchmark_id for record in records}

    candidate_payload = yaml.safe_load(CANDIDATE_BANK.read_text(encoding="utf-8"))
    candidate_ids = {candidate["benchmark_id"] for candidate in candidate_payload["candidates"]}

    assert len(research_ids) == len(records)
    assert research_ids == candidate_ids


def test_tier1_candidates_all_have_verified_structured_source_research() -> None:
    records = {
        record.benchmark_id: record
        for record in load_benchmark_source_research_manifest(MANIFEST)
    }

    tier1 = [records[benchmark_id] for benchmark_id in ("BMARK-001", "BMARK-002", "BMARK-003")]

    assert [record.benchmark_id for record in tier1] == ["BMARK-001", "BMARK-002", "BMARK-003"]
    assert all(record.finding != "not_checked" for record in tier1)
    assert all(record.source_page_url is not None for record in tier1)
    assert all(record.source_title is not None for record in tier1)
    assert tier1[0].finding == "official_commercial_guitar_pro"
    assert tier1[1].finding == "other_structured_notation"
    assert tier1[2].finding == "other_structured_notation"
