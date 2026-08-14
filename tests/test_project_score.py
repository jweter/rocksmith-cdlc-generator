from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import project_score
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_intake import SourceRightsClass
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def _fake_inventory(path: Path, *, imported_relative_path: str | None = None) -> ProjectScoreSource:
    return ProjectScoreSource(
        source_filename=path.name,
        source_sha256=sha256_file(path),
        source_format="gp5",
        imported_relative_path=imported_relative_path or path.name,
        tracks=[
            ScoreTrackCandidate(
                source_track_index=0,
                name="Bass",
                instrument_hint="bass",
                tuning_midi=[28, 33, 38, 43],
                note_count=12,
            )
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=0,
                confidence=0.99,
                basis=["track name contains bass"],
                human_confirmed=False,
            )
        ],
    )


def test_register_score_copies_immutable_source_and_persists_reviewable_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    source = tmp_path / "Full Score.gp5"
    source.write_bytes(b"score-v1")
    monkeypatch.setattr(project_score, "inventory_score", _fake_inventory)

    result = project_score.register_project_score(
        project,
        source,
        rights_class=SourceRightsClass.unknown,
    )

    stored = Path(result.stored_source_path)
    contract = ProjectScoreSource.read_json(Path(result.score_source_path))
    receipt = SourceIntakeReceipt.model_validate_json(
        Path(result.intake_receipt_path).read_text(encoding="utf-8")
    )

    assert stored.read_bytes() == b"score-v1"
    assert stored.is_relative_to(project)
    assert contract.source_sha256 == sha256_file(source)
    assert contract.imported_relative_path == str(stored.relative_to(project))
    assert contract.mapping_for(ArrangementRole.bass) is not None
    assert contract.mapping_for(ArrangementRole.bass).human_confirmed is False
    assert contract.mapping_for(ArrangementRole.bass).requires_human_review is True
    assert receipt.route_action == "register_score_source"
    assert receipt.source_sha256 == contract.source_sha256
    assert receipt.descriptor.rights_class is SourceRightsClass.unknown
    assert result.human_rights_review_required is True


def test_register_same_score_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    source = tmp_path / "song.gp5"
    source.write_bytes(b"same-score")
    monkeypatch.setattr(project_score, "inventory_score", _fake_inventory)

    first = project_score.register_project_score(project, source)
    second = project_score.register_project_score(project, source)

    assert second.stored_source_path == first.stored_source_path
    assert second.score_source_path == first.score_source_path
    assert sha256_file(Path(second.stored_source_path)) == sha256_file(source)


def test_register_different_score_requires_explicit_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    first = tmp_path / "first.gp5"
    second = tmp_path / "second.gp5"
    first.write_bytes(b"first-score")
    second.write_bytes(b"second-score")
    monkeypatch.setattr(project_score, "inventory_score", _fake_inventory)

    project_score.register_project_score(project, first)

    with pytest.raises(ValueError, match="different registered score"):
        project_score.register_project_score(project, second)


def test_streaming_reference_rights_cannot_register_local_score_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    source = tmp_path / "song.gp5"
    source.write_bytes(b"score")
    monkeypatch.setattr(project_score, "inventory_score", _fake_inventory)

    with pytest.raises(ValueError, match="streaming-reference-only"):
        project_score.register_project_score(
            project,
            source,
            rights_class=SourceRightsClass.streaming_reference_only,
        )
