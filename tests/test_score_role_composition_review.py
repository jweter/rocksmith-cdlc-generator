from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_mapping_review import confirm_score_mapping
from rocksmith_cdlc_generator.score_role_composition_review import (
    SCORE_ROLE_COMPOSITION_PATH,
    load_current_score_role_composition,
    record_score_role_composition,
)
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)


def _project_with_score(tmp_path: Path) -> Path:
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
            ScoreTrackCandidate(source_track_index=0, name="Lead", instrument_hint="guitar", note_count=100),
            ScoreTrackCandidate(source_track_index=1, name="Solo", instrument_hint="guitar", note_count=30),
            ScoreTrackCandidate(source_track_index=2, name="Rhythm", instrument_hint="guitar", note_count=120),
            ScoreTrackCandidate(source_track_index=3, name="Clean", instrument_hint="guitar", note_count=20),
            ScoreTrackCandidate(source_track_index=4, name="Bass", instrument_hint="bass", note_count=90),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(role="lead", source_track_index=0, confidence=0.9, human_confirmed=True),
            ScoreArrangementMapping(role="rhythm", source_track_index=2, confidence=0.9, human_confirmed=True),
            ScoreArrangementMapping(role="bass", source_track_index=4, confidence=0.9, human_confirmed=True),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")
    return project


def test_records_and_loads_current_composition(tmp_path: Path) -> None:
    project = _project_with_score(tmp_path)

    recorded = record_score_role_composition(
        project,
        selections={
            ArrangementRole.lead: [0, 1],
            ArrangementRole.rhythm: [2, 3],
            ArrangementRole.bass: [4],
        },
    )
    loaded = load_current_score_role_composition(project)

    assert loaded == recorded
    assert (project / SCORE_ROLE_COMPOSITION_PATH).is_file()
    assert loaded.selection_for(ArrangementRole.lead).source_track_indices == [0, 1]


def test_missing_composition_is_explicit_none(tmp_path: Path) -> None:
    project = _project_with_score(tmp_path)

    assert load_current_score_role_composition(project) is None


def test_mapping_change_makes_persisted_composition_fail_closed(tmp_path: Path) -> None:
    project = _project_with_score(tmp_path)
    record_score_role_composition(
        project,
        selections={ArrangementRole.lead: [0, 1]},
    )

    confirm_score_mapping(project, role=ArrangementRole.lead, source_track_index=1)

    with pytest.raises(ValueError, match="primary first track"):
        load_current_score_role_composition(project)


def test_explicit_rewrite_after_mapping_change_uses_new_primary(tmp_path: Path) -> None:
    project = _project_with_score(tmp_path)
    record_score_role_composition(project, selections={ArrangementRole.lead: [0, 1]})
    confirm_score_mapping(project, role=ArrangementRole.lead, source_track_index=1)

    updated = record_score_role_composition(
        project,
        selections={ArrangementRole.lead: [1, 0]},
    )

    assert updated.selection_for(ArrangementRole.lead).source_track_indices == [1, 0]
    assert load_current_score_role_composition(project) == updated


def test_writer_rejects_unknown_extra_without_replacing_existing_plan(tmp_path: Path) -> None:
    project = _project_with_score(tmp_path)
    original = record_score_role_composition(
        project,
        selections={ArrangementRole.lead: [0, 1]},
    )
    before = (project / SCORE_ROLE_COMPOSITION_PATH).read_bytes()

    with pytest.raises(ValueError, match="unknown score track"):
        record_score_role_composition(
            project,
            selections={ArrangementRole.lead: [0, 99]},
        )

    assert (project / SCORE_ROLE_COMPOSITION_PATH).read_bytes() == before
    assert load_current_score_role_composition(project) == original
