from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    CorpusEvidenceObservation,
    PrivateProductRealityScenario,
    RoleTimingObservation,
    SharedTimingExpectations,
    SharedTimingObservation,
    _collect_corpus_evidence,
    evaluate_shared_timing_observation,
    load_private_product_reality_scenario,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64


def _scenario(project: Path, corpus: Path | None = None) -> PrivateProductRealityScenario:
    return PrivateProductRealityScenario(
        scenario_id="corpus-integration",
        project_dir=project,
        corpus_inventory_path=corpus,
        expected=SharedTimingExpectations(first_playable_seconds=7.13),
    )


def _role(role: ArrangementRole) -> RoleTimingObservation:
    return RoleTimingObservation(
        role=role,
        source_track_index={
            ArrangementRole.bass: 0,
            ArrangementRole.lead: 1,
            ArrangementRole.rhythm: 2,
        }[role],
        first_source_seconds=4.0,
        first_playable_seconds=7.13,
        note_count=10,
        recording_sha256=_HASH_A,
        score_sha256=_HASH_B,
        source_output_sha256=_HASH_C,
        timing_points_sha256=_HASH_D,
    )


def _passing_observation(project: Path, corpus: CorpusEvidenceObservation | None = None) -> SharedTimingObservation:
    return SharedTimingObservation(
        scenario_id="corpus-integration",
        project_dir=str(project),
        observed_at_utc="2026-09-17T20:00:00+00:00",
        build=BuildObservation(
            version="0.1.0",
            commit_sha="1" * 40,
            packaged=True,
        ),
        project_recording_sha256=_HASH_A,
        tempo_map_sha256=_HASH_C,
        tempo_beat_count=100,
        corpus_evidence=corpus,
        roles=[
            _role(ArrangementRole.bass),
            _role(ArrangementRole.lead),
            _role(ArrangementRole.rhythm),
        ],
    )


def test_missing_corpus_config_does_not_block_existing_timing_lane(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    evidence = evaluate_shared_timing_observation(
        scenario,
        _passing_observation(tmp_path),
        scenario_sha256="e" * 64,
    )

    assert evidence.result == "PASS"
    assert evidence.corpus_evidence is None
    assert not any(check.code == "private_corpus_authority" for check in evidence.checks)


def test_relative_private_corpus_path_resolves_next_to_scenario(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir()
    scenario_path = private_root / "scenario.json"
    scenario_path.write_text(
        _scenario(Path("project"), Path("corpus/inventory.json")).model_dump_json(indent=2),
        encoding="utf-8",
    )

    loaded = load_private_product_reality_scenario(scenario_path)

    assert loaded.project_dir == (private_root / "project").resolve()
    assert loaded.corpus_inventory_path == (private_root / "corpus" / "inventory.json").resolve()


def test_valid_private_inventory_exports_only_repository_safe_aggregate_summary(tmp_path: Path) -> None:
    inventory_path = tmp_path / "Private Artist - Private Song.inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "relative_path": "Private Artist - Private Song.psarc",
                        "sha256": "f" * 64,
                        "size_bytes": 1234,
                        "trust_tier": "C",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    scenario = _scenario(tmp_path, inventory_path)

    summary, error = _collect_corpus_evidence(scenario)

    assert error is None
    assert summary is not None
    assert summary.item_count == 1
    assert summary.total_bytes == 1234
    assert summary.trust_tier_counts == {"A": 0, "B": 0, "C": 1}
    serialized = summary.model_dump_json()
    assert "Private Artist" not in serialized
    assert "Private Song" not in serialized
    assert str(inventory_path) not in serialized
    assert "relative_path" not in serialized


def test_configured_malformed_corpus_fails_closed_without_leaking_private_details(tmp_path: Path) -> None:
    inventory_path = tmp_path / "Secret Song.inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "relative_path": "Secret Artist - Secret Song.psarc",
                        "sha256": "not-a-hash",
                        "size_bytes": 1234,
                        "trust_tier": "C",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    summary, error = _collect_corpus_evidence(_scenario(tmp_path, inventory_path))

    assert summary is None
    assert error is not None
    assert "unavailable or invalid" in error
    assert "Secret Song" not in error
    assert "Secret Artist" not in error
    assert str(inventory_path) not in error


def test_safe_corpus_summary_becomes_bound_product_reality_evidence(tmp_path: Path) -> None:
    corpus = CorpusEvidenceObservation(
        item_count=3,
        total_bytes=3000,
        trust_tier_counts={"A": 1, "B": 1, "C": 1},
        corpus_sha256="9" * 64,
    )
    scenario = _scenario(tmp_path)

    evidence = evaluate_shared_timing_observation(
        scenario,
        _passing_observation(tmp_path, corpus),
        scenario_sha256="e" * 64,
    )

    assert evidence.result == "PASS"
    assert evidence.corpus_evidence == corpus
    check = next(check for check in evidence.checks if check.code == "private_corpus_authority")
    assert check.status == "PASS"
    assert check.observed == 3
    serialized = evidence.model_dump_json()
    assert "relative_path" not in serialized
    assert "Private Artist" not in serialized
