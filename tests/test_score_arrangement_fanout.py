from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import score_arrangement_fanout
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_arrangement_fanout import (
    ConfirmedScoreArrangementManifest,
    import_confirmed_score_arrangements,
)
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)


def _project_with_score(tmp_path: Path, *, confirmed: bool = True) -> tuple[Path, ProjectScoreSource]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    stored = project / "sources" / "score" / "original" / "song.musicxml"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"score")
    digest = sha256_file(stored)
    score = ProjectScoreSource(
        source_filename="song.musicxml",
        source_sha256=digest,
        source_format="musicxml",
        imported_relative_path=str(stored.relative_to(project)),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead", note_count=10),
            ScoreTrackCandidate(source_track_index=1, name="Rhythm", note_count=20),
            ScoreTrackCandidate(source_track_index=2, name="Bass", note_count=15),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.9,
                human_confirmed=confirmed,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=1,
                confidence=0.8,
                human_confirmed=confirmed,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=1.0,
                human_confirmed=False,
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")
    return project, score


def _write_import(project: Path, score: ProjectScoreSource, role: ArrangementRole, index: int) -> Path:
    output = project / "sources" / "imported" / f"{role.value}.json"
    imported = ImportedSource(
        provenance=SourceProvenance(
            source_type="musicxml",
            source_filename=score.source_filename,
            source_sha256=score.source_sha256,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=index,
                instrument=role.value,
                notes=[
                    SourceNoteEvent(
                        start_seconds=0,
                        duration_seconds=1,
                        midi=60,
                        import_confidence=1,
                    )
                ],
            )
        ],
    )
    return imported.write_json(output)


def test_fanout_imports_only_human_confirmed_mappings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, score = _project_with_score(tmp_path)
    monkeypatch.setattr(score_arrangement_fanout, "_registered_score_rights_are_resolved", lambda *_: True)
    calls: list[tuple[ArrangementRole, int]] = []

    def fake_import(project_path: Path, source_path: Path, loaded: ProjectScoreSource, *, role: ArrangementRole, source_track_index: int) -> Path:
        assert source_path.read_bytes() == b"score"
        calls.append((role, source_track_index))
        return _write_import(project_path, loaded, role, source_track_index)

    monkeypatch.setattr(score_arrangement_fanout, "_import_one", fake_import)

    result = import_confirmed_score_arrangements(project)
    manifest = ConfirmedScoreArrangementManifest.model_validate_json(
        Path(result.manifest_path).read_text(encoding="utf-8")
    )

    assert calls == [(ArrangementRole.lead, 0), (ArrangementRole.rhythm, 1)]
    assert set(result.arrangements) == {ArrangementRole.lead, ArrangementRole.rhythm}
    assert [(entry.role, entry.source_track_index) for entry in manifest.arrangements] == calls
    assert manifest.source_sha256 == score.source_sha256


def test_fanout_requires_resolved_score_rights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = _project_with_score(tmp_path)
    monkeypatch.setattr(score_arrangement_fanout, "_registered_score_rights_are_resolved", lambda *_: False)

    with pytest.raises(PermissionError, match="rights/provenance review is unresolved"):
        import_confirmed_score_arrangements(project)


def test_fanout_requires_at_least_one_human_confirmed_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = _project_with_score(tmp_path, confirmed=False)
    monkeypatch.setattr(score_arrangement_fanout, "_registered_score_rights_are_resolved", lambda *_: True)

    with pytest.raises(ValueError, match="no human-confirmed"):
        import_confirmed_score_arrangements(project)


def test_invalid_import_never_publishes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, score = _project_with_score(tmp_path)
    monkeypatch.setattr(score_arrangement_fanout, "_registered_score_rights_are_resolved", lambda *_: True)

    def wrong_import(project_path: Path, source_path: Path, loaded: ProjectScoreSource, *, role: ArrangementRole, source_track_index: int) -> Path:
        return _write_import(project_path, loaded, ArrangementRole.bass, source_track_index)

    monkeypatch.setattr(score_arrangement_fanout, "_import_one", wrong_import)

    with pytest.raises(ValueError, match="human-confirmed role"):
        import_confirmed_score_arrangements(project)

    manifest = project / "sources" / "imported" / f"score-arrangements-{score.source_sha256[:12]}.json"
    assert not manifest.exists()
