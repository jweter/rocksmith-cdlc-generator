"""End-to-end CLI wiring for issue #232's persisted per-role composition fan-out.

`cdlc-score-composition` plumbs the already-tested library functions in
score_role_composition_review.py, score_role_composition_fanout_review.py, and
score_role_composition_overlap_review.py through to a human-usable command line: build
the composition plan, preview cross-track overlap evidence, record explicit human
overlap decisions, and compose/persist the fan-out artifact (review/score_role_composition_fanout.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator import score_role_composition_fanout_review as fanout_review
from rocksmith_cdlc_generator import score_role_composition_cli as cli
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_role_composition_fanout_review import (
    SCORE_ROLE_COMPOSITION_FANOUT_PATH,
)
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceNoteEvent, SourceProvenance, SourceTrack
from rocksmith_cdlc_generator.source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
)
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt

_NON_OVERLAPPING_TRACK_NOTES: dict[int, list[SourceNoteEvent]] = {
    1: [
        SourceNoteEvent(start_seconds=0.0, duration_seconds=0.5, midi=40, import_confidence=1.0),
        SourceNoteEvent(start_seconds=1.0, duration_seconds=0.5, midi=42, import_confidence=1.0),
    ],
    3: [
        SourceNoteEvent(start_seconds=0.5, duration_seconds=0.5, midi=45, import_confidence=1.0),
    ],
}
_OVERLAPPING_TRACK_NOTES: dict[int, list[SourceNoteEvent]] = {
    1: [
        SourceNoteEvent(
            start_seconds=1.0, duration_seconds=0.5, midi=52, string_index=1, fret=2, import_confidence=1.0
        )
    ],
    3: [
        SourceNoteEvent(
            start_seconds=1.0, duration_seconds=0.5, midi=52, string_index=1, fret=2, import_confidence=1.0
        )
    ],
}


def _project_with_score(tmp_path: Path) -> tuple[Path, str]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")

    stored = project / "sources" / "score" / "original" / "song.musicxml"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"complete-score")
    digest = sha256_file(stored)

    score = ProjectScoreSource(
        source_filename="song.musicxml",
        source_sha256=digest,
        source_format="musicxml",
        imported_relative_path=stored.relative_to(project).as_posix(),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead", note_count=10),
            ScoreTrackCandidate(source_track_index=1, name="Rhythm 1", note_count=10),
            ScoreTrackCandidate(source_track_index=2, name="Bass", note_count=10),
            ScoreTrackCandidate(source_track_index=3, name="Rhythm 2", note_count=10),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead, source_track_index=0, confidence=0.9, human_confirmed=True
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm, source_track_index=1, confidence=0.9, human_confirmed=True
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")

    descriptor = SourceIntakeDescriptor(
        display_name="song.musicxml",
        source_format=SourceFormat.musicxml,
        family=SourceFamily.notation,
        adapter_status=AdapterStatus.supported,
        rights_class=SourceRightsClass.user_owned_local,
        local_bytes_available=True,
    )
    receipt = SourceIntakeReceipt(
        descriptor=descriptor,
        route_action="register_score_source",
        route_reason="test score registration",
        source_sha256=digest,
        output_relative_path=stored.relative_to(project).as_posix(),
    )
    receipt_path = project / "sources" / "intake" / f"song-{digest[:12]}-score.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return project, digest


def _install_fake_musicxml_importer(
    monkeypatch: pytest.MonkeyPatch,
    digest: str,
    *,
    notes_by_track: dict[int, list[SourceNoteEvent]],
) -> None:
    def fake_import(path: Path, *, part_index: int | None = None, instrument: str = "bass") -> ImportedSource:
        assert part_index is not None
        return ImportedSource(
            provenance=SourceProvenance(
                source_type="musicxml",
                source_filename=path.name,
                source_sha256=digest,
                importer="test",
                importer_version="1",
            ),
            tracks=[
                SourceTrack(
                    source_track_index=part_index,
                    name=f"Track {part_index}",
                    instrument=instrument,
                    notes=notes_by_track[part_index],
                )
            ],
        )

    monkeypatch.setattr(fanout_review, "import_musicxml", fake_import)


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr("sys.argv", ["cdlc-score-composition", *args])
    cli.main()


def test_parser_rejects_unknown_role() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["projects/song", "plan-select", "drums", "0"])


def test_plan_show_prints_null_before_any_plan_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project, _digest = _project_with_score(tmp_path)

    _run(monkeypatch, str(project), "plan-show")

    assert capsys.readouterr().out.strip() == "null"


def test_plan_select_preserves_other_roles_current_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project, _digest = _project_with_score(tmp_path)

    _run(monkeypatch, str(project), "plan-select", "lead", "0")
    capsys.readouterr()
    _run(monkeypatch, str(project), "plan-select", "rhythm", "1", "3")
    plan = json.loads(capsys.readouterr().out)

    selections = {item["role"]: item["source_track_indices"] for item in plan["selections"]}
    assert selections == {"lead": [0], "rhythm": [1, 3]}


def test_overlaps_command_reports_current_selection_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_OVERLAPPING_TRACK_NOTES)
    _run(monkeypatch, str(project), "plan-select", "rhythm", "1", "3")
    capsys.readouterr()

    _run(monkeypatch, str(project), "overlaps", "rhythm")
    report = json.loads(capsys.readouterr().out)

    assert report["roles"][0]["overlap_count"] == 1
    assert report["roles"][0]["overlaps"][0]["kind"] == "exact_duplicate"
    assert not (project / SCORE_ROLE_COMPOSITION_FANOUT_PATH).exists()


def test_compose_without_overlaps_needs_no_decisions_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_NON_OVERLAPPING_TRACK_NOTES)
    _run(monkeypatch, str(project), "plan-select", "rhythm", "1", "3")
    capsys.readouterr()

    _run(monkeypatch, str(project), "compose", "rhythm")
    record = json.loads(capsys.readouterr().out)

    assert record["source_track_indices"] == [1, 3]
    assert (project / SCORE_ROLE_COMPOSITION_FANOUT_PATH).is_file()

    capsys.readouterr()
    _run(monkeypatch, str(project), "compose-show")
    layer = json.loads(capsys.readouterr().out)
    assert layer["records"][0]["role"] == "rhythm"


def test_compose_without_decisions_fails_closed_on_unresolved_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_OVERLAPPING_TRACK_NOTES)
    _run(monkeypatch, str(project), "plan-select", "rhythm", "1", "3")

    with pytest.raises(ValueError, match="unresolved overlap"):
        _run(monkeypatch, str(project), "compose", "rhythm")

    assert not (project / SCORE_ROLE_COMPOSITION_FANOUT_PATH).exists()


def test_compose_with_a_decisions_file_resolves_reported_overlaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project, digest = _project_with_score(tmp_path)
    _install_fake_musicxml_importer(monkeypatch, digest, notes_by_track=_OVERLAPPING_TRACK_NOTES)
    _run(monkeypatch, str(project), "plan-select", "rhythm", "1", "3")
    capsys.readouterr()

    _run(monkeypatch, str(project), "overlaps", "rhythm")
    report = json.loads(capsys.readouterr().out)
    overlap = report["roles"][0]["overlaps"][0]

    decisions_path = tmp_path / "decisions.json"
    decisions_path.write_text(
        json.dumps({"decisions": [{"role": "rhythm", "overlap": overlap, "resolution": "keep_left"}]}),
        encoding="utf-8",
    )

    _run(monkeypatch, str(project), "compose", "rhythm", "--decisions", str(decisions_path))
    record = json.loads(capsys.readouterr().out)

    # keep_left drops track 3's losing event, leaving only track 1's note at this overlap.
    assert [(n["source_track_index"], n["event_index"]) for n in record["notes"]] == [(1, 0)]


def test_compose_show_prints_null_before_any_fanout_is_composed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project, _digest = _project_with_score(tmp_path)

    _run(monkeypatch, str(project), "compose-show")

    assert capsys.readouterr().out.strip() == "null"
