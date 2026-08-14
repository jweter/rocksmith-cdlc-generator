from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from rocksmith_cdlc_generator import score_fanout
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_fanout import (
    ScoreFanoutManifest,
    fanout_confirmed_score_mappings,
)
from rocksmith_cdlc_generator.score_mapping_review import confirm_score_mapping
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceProvenance, SourceTrack
from rocksmith_cdlc_generator.source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
)
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt


def _project_with_score(
    tmp_path: Path,
    *,
    rights_class: SourceRightsClass = SourceRightsClass.user_owned_local,
) -> tuple[Path, Path, str]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")

    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"complete-score")
    digest = sha256_file(stored)

    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path=stored.relative_to(project).as_posix(),
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
                human_confirmed=True,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=1,
                confidence=0.95,
                basis=["track name contains rhythm"],
                human_confirmed=True,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=1.0,
                basis=["track name contains bass"],
                human_confirmed=False,
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")

    descriptor = SourceIntakeDescriptor(
        display_name="song.gp5",
        source_format=SourceFormat.gp5,
        family=SourceFamily.notation,
        adapter_status=AdapterStatus.optional_dependency,
        rights_class=rights_class,
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
    return project, stored, digest


def _write_fake_import(
    project_dir: Path,
    gp_path: Path,
    *,
    digest: str,
    track_index: int,
    instrument: str,
) -> Path:
    assert sha256_file(gp_path) == digest
    output = project_dir / "sources" / "imported" / f"fake-{instrument}.json"
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename=gp_path.name,
            source_sha256=digest,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=track_index,
                instrument=instrument,
                notes=[],
            )
        ],
    ).write_json(output)
    return output


def _install_fake_gp_importer(monkeypatch: pytest.MonkeyPatch, digest: str) -> list[tuple[str, int]]:
    calls: list[tuple[str, int]] = []

    def fake_import(
        project_dir: Path,
        gp_path: Path,
        *,
        track_index: int | None = None,
        instrument: str = "bass",
    ) -> Path:
        assert track_index is not None
        calls.append((instrument, track_index))
        return _write_fake_import(
            project_dir,
            gp_path,
            digest=digest,
            track_index=track_index,
            instrument=instrument,
        )

    monkeypatch.setattr(score_fanout, "import_project_guitarpro", fake_import)
    return calls


def test_fanout_imports_only_human_confirmed_mappings_and_publishes_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _, digest = _project_with_score(tmp_path)
    calls = _install_fake_gp_importer(monkeypatch, digest)

    result = fanout_confirmed_score_mappings(project)
    manifest = ScoreFanoutManifest.model_validate_json(
        Path(result.manifest_path).read_text(encoding="utf-8")
    )

    assert calls == [("lead", 0), ("rhythm", 1)]
    assert set(result.outputs) == {"lead", "rhythm"}
    assert manifest.score_source_sha256 == digest
    assert [(entry.role.value, entry.source_track_index) for entry in manifest.arrangements] == [
        ("lead", 0),
        ("rhythm", 1),
    ]
    assert all((project / entry.output_json).is_file() for entry in manifest.arrangements)


def test_requested_unconfirmed_mapping_stops_before_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _, digest = _project_with_score(tmp_path)
    calls = _install_fake_gp_importer(monkeypatch, digest)

    with pytest.raises(ValueError, match="bass score mapping is not human-confirmed"):
        fanout_confirmed_score_mappings(project, roles=[ArrangementRole.bass])

    assert calls == []


def test_unreviewed_unknown_score_rights_stop_before_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _, digest = _project_with_score(tmp_path, rights_class=SourceRightsClass.unknown)
    calls = _install_fake_gp_importer(monkeypatch, digest)

    with pytest.raises(ValueError, match="rights/provenance still require human review"):
        fanout_confirmed_score_mappings(project)

    assert calls == []


def test_failed_fanout_removes_stale_authority_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _, digest = _project_with_score(tmp_path)
    manifest = project / "sources" / "imported" / f"score-fanout-{digest[:12]}.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("stale", encoding="utf-8")

    def failing_import(*args, **kwargs):
        raise RuntimeError("synthetic importer failure")

    monkeypatch.setattr(score_fanout, "import_project_guitarpro", failing_import)

    with pytest.raises(RuntimeError, match="synthetic importer failure"):
        fanout_confirmed_score_mappings(project)

    assert not manifest.exists()


def test_tampered_registered_score_stops_before_fanout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, stored, digest = _project_with_score(tmp_path)
    calls = _install_fake_gp_importer(monkeypatch, digest)
    stored.write_bytes(b"tampered")

    with pytest.raises(IOError, match="do not match"):
        fanout_confirmed_score_mappings(project)

    assert calls == []


def test_remapping_after_fanout_invalidates_authority_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _, digest = _project_with_score(tmp_path)
    _install_fake_gp_importer(monkeypatch, digest)

    result = fanout_confirmed_score_mappings(project)
    manifest = Path(result.manifest_path)
    assert manifest.is_file()

    confirm_score_mapping(
        project,
        role=ArrangementRole.lead,
        source_track_index=2,
    )

    assert not manifest.exists()


def test_mapping_confirmation_waits_for_fanout_then_invalidates_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _, digest = _project_with_score(tmp_path)
    importer_entered = Event()
    importer_release = Event()

    def blocking_import(
        project_dir: Path,
        gp_path: Path,
        *,
        track_index: int | None = None,
        instrument: str = "bass",
    ) -> Path:
        assert track_index is not None
        if instrument == "lead":
            importer_entered.set()
            assert importer_release.wait(timeout=2)
        return _write_fake_import(
            project_dir,
            gp_path,
            digest=digest,
            track_index=track_index,
            instrument=instrument,
        )

    monkeypatch.setattr(score_fanout, "import_project_guitarpro", blocking_import)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fanout_future = pool.submit(fanout_confirmed_score_mappings, project)
        assert importer_entered.wait(timeout=1)
        remap_future = pool.submit(
            confirm_score_mapping,
            project,
            role=ArrangementRole.lead,
            source_track_index=2,
        )
        time.sleep(0.05)
        assert not remap_future.done()

        importer_release.set()
        fanout_result = fanout_future.result(timeout=2)
        remap = remap_future.result(timeout=2)

    assert remap.source_track_index == 2
    assert not Path(fanout_result.manifest_path).exists()
