from __future__ import annotations

import os
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rocksmith_cdlc_generator import score_mapping_review
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_mapping_review import (
    confirm_score_mapping,
    load_score_for_mapping_review,
)
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)


def _project_with_score(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"complete-score")
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=sha256_file(stored),
        source_format="gp5",
        imported_relative_path=str(stored.relative_to(project)),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead Guitar", note_count=100),
            ScoreTrackCandidate(source_track_index=1, name="Rhythm Guitar", note_count=120),
            ScoreTrackCandidate(source_track_index=2, name="Bass", note_count=90),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.98,
                basis=["track name contains lead"],
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=1.0,
                basis=["track name contains bass"],
            ),
        ],
    )
    contract = project / "sources" / "score" / "source.json"
    score.write_json(contract)
    return project, stored


def test_confirming_proposed_track_preserves_importer_evidence(tmp_path: Path) -> None:
    project, _ = _project_with_score(tmp_path)

    confirmed = confirm_score_mapping(
        project,
        role=ArrangementRole.lead,
        source_track_index=0,
    )
    restored = load_score_for_mapping_review(project)

    assert confirmed.human_confirmed is True
    assert confirmed.confidence == 0.98
    assert confirmed.basis == ["track name contains lead"]
    assert restored.mapping_for(ArrangementRole.lead) == confirmed
    assert restored.mapping_for(ArrangementRole.bass).human_confirmed is False


def test_human_can_replace_proposal_with_another_known_track(tmp_path: Path) -> None:
    project, _ = _project_with_score(tmp_path)

    confirmed = confirm_score_mapping(
        project,
        role=ArrangementRole.lead,
        source_track_index=1,
    )

    assert confirmed.source_track_index == 1
    assert confirmed.human_confirmed is True
    assert confirmed.confidence == 0.0
    assert confirmed.basis == ["human selected score track explicitly"]


def test_concurrent_confirmations_preserve_both_roles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = _project_with_score(tmp_path)
    original_load = score_mapping_review.load_score_for_mapping_review

    def slow_load(path: Path) -> ProjectScoreSource:
        score = original_load(path)
        time.sleep(0.05)
        return score

    monkeypatch.setattr(score_mapping_review, "load_score_for_mapping_review", slow_load)

    with ThreadPoolExecutor(max_workers=2) as pool:
        lead = pool.submit(
            score_mapping_review.confirm_score_mapping,
            project,
            role=ArrangementRole.lead,
            source_track_index=0,
        )
        rhythm = pool.submit(
            score_mapping_review.confirm_score_mapping,
            project,
            role=ArrangementRole.rhythm,
            source_track_index=1,
        )
        lead.result()
        rhythm.result()

    restored = original_load(project)
    assert restored.mapping_for(ArrangementRole.lead).human_confirmed is True
    assert restored.mapping_for(ArrangementRole.rhythm).human_confirmed is True
    assert restored.mapping_for(ArrangementRole.lead).source_track_index == 0
    assert restored.mapping_for(ArrangementRole.rhythm).source_track_index == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not portable to Windows")
def test_mapping_confirmation_preserves_contract_permissions(tmp_path: Path) -> None:
    project, _ = _project_with_score(tmp_path)
    contract = project / "sources" / "score" / "source.json"
    os.chmod(contract, 0o664)
    before = stat.S_IMODE(contract.stat().st_mode)

    confirm_score_mapping(project, role=ArrangementRole.bass, source_track_index=2)

    assert stat.S_IMODE(contract.stat().st_mode) == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX group ownership is not portable to Windows")
def test_atomic_replacement_requests_original_contract_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = _project_with_score(tmp_path)
    contract = project / "sources" / "score" / "source.json"
    original_gid = contract.stat().st_gid
    calls: list[tuple[int, int]] = []
    real_chown = os.chown

    def recording_chown(path: os.PathLike[str] | str, uid: int, gid: int) -> None:
        calls.append((uid, gid))
        real_chown(path, uid, gid)

    monkeypatch.setattr(score_mapping_review.os, "chown", recording_chown)

    confirm_score_mapping(project, role=ArrangementRole.bass, source_track_index=2)

    assert calls == [(-1, original_gid)]
    assert contract.stat().st_gid == original_gid


@pytest.mark.skipif(os.name == "nt", reason="POSIX group ownership is not portable to Windows")
def test_group_preservation_failure_does_not_replace_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = _project_with_score(tmp_path)
    contract = project / "sources" / "score" / "source.json"
    before = contract.read_bytes()

    def refuse_chown(path: os.PathLike[str] | str, uid: int, gid: int) -> None:
        raise PermissionError("cannot preserve shared group")

    monkeypatch.setattr(score_mapping_review.os, "chown", refuse_chown)

    with pytest.raises(PermissionError, match="preserve shared group"):
        confirm_score_mapping(project, role=ArrangementRole.bass, source_track_index=2)

    assert contract.read_bytes() == before
    assert ProjectScoreSource.read_json(contract).mapping_for(ArrangementRole.bass).human_confirmed is False


def test_unknown_track_cannot_be_confirmed(tmp_path: Path) -> None:
    project, _ = _project_with_score(tmp_path)

    with pytest.raises(ValueError, match="does not exist"):
        confirm_score_mapping(project, role=ArrangementRole.rhythm, source_track_index=99)


def test_mapping_review_refuses_tampered_registered_score(tmp_path: Path) -> None:
    project, stored = _project_with_score(tmp_path)
    stored.write_bytes(b"tampered")

    with pytest.raises(IOError, match="do not match"):
        confirm_score_mapping(project, role=ArrangementRole.bass, source_track_index=2)


def test_mapping_review_refuses_contract_path_outside_project(tmp_path: Path) -> None:
    project, _ = _project_with_score(tmp_path)
    outside = tmp_path / "outside.gp5"
    outside.write_bytes(b"complete-score")
    contract_path = project / "sources" / "score" / "source.json"
    score = ProjectScoreSource.read_json(contract_path).model_copy(
        update={"imported_relative_path": "../outside.gp5"}
    )
    score.write_json(contract_path)

    with pytest.raises(ValueError, match="inside the project"):
        load_score_for_mapping_review(project)
