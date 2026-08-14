from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.source_intake import SourceRightsClass
from rocksmith_cdlc_generator.source_workflow import add_local_source


def _file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"fixture")
    return path


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def _write_audio_manifest(project: Path, source: Path) -> None:
    ProjectManifest(
        project_name="Song",
        title="Song",
        source_original_path=str(source),
        source_project_path=f"source/{source.name}",
        source_sha256=sha256_file(source),
        source_metadata=AudioMetadata(
            duration_seconds=1.0,
            sample_rate_hz=44_100,
            channels=2,
        ),
    ).save(project)


def test_audio_source_creates_project_and_persists_completed_ingest_hash(tmp_path: Path, monkeypatch) -> None:
    source = _file(tmp_path, "song.flac")
    created = tmp_path / "projects" / "song"
    created.mkdir(parents=True)
    calls: dict[str, object] = {}

    def fake_create_project(**kwargs):
        calls.update(kwargs)
        _write_audio_manifest(created, source)
        return created

    monkeypatch.setattr("rocksmith_cdlc_generator.source_workflow.create_project", fake_create_project)

    result = add_local_source(
        source,
        title="Song",
        artist="Artist",
        projects_root=tmp_path / "projects",
        rights_class=SourceRightsClass.user_owned_local,
        instruments=["bass", "rhythm"],
    )

    assert result.status == "complete"
    assert result.route.action == "project_audio"
    assert result.output_path == str(created.resolve())
    assert result.human_rights_review_required is False
    assert calls["audio"] == source.resolve()
    assert calls["instruments"] == ["bass", "rhythm"]

    receipt_path = Path(result.intake_receipt_path or "")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest = ProjectManifest.load(created)
    assert receipt["descriptor"]["rights_class"] == "user_owned_local"
    assert receipt["descriptor"]["source_format"] == "flac"
    assert receipt["source_sha256"] == manifest.source_sha256


def test_audio_source_change_during_ingest_refuses_mismatched_receipt(tmp_path: Path, monkeypatch) -> None:
    source = _file(tmp_path, "song.flac")
    created = tmp_path / "project"
    created.mkdir()

    def fake_create_project(**kwargs):
        _write_audio_manifest(created, source)
        source.write_bytes(b"changed-after-ingest")
        return created

    monkeypatch.setattr("rocksmith_cdlc_generator.source_workflow.create_project", fake_create_project)

    with pytest.raises(IOError, match="changed during ingest"):
        add_local_source(source, title="Song")

    assert not (created / "sources" / "intake").exists()


def test_unknown_rights_remain_reviewable_without_blocking_local_audio(tmp_path: Path, monkeypatch) -> None:
    source = _file(tmp_path, "song.mp3")
    created = tmp_path / "project"
    created.mkdir()

    def fake_create_project(**kwargs):
        _write_audio_manifest(created, source)
        return created

    monkeypatch.setattr("rocksmith_cdlc_generator.source_workflow.create_project", fake_create_project)

    result = add_local_source(source, title="Song")

    assert result.status == "complete"
    assert result.human_rights_review_required is True
    assert result.intake_receipt_path is not None


def test_symbolic_source_requires_existing_project(tmp_path: Path) -> None:
    source = _file(tmp_path, "bass.mid")

    with pytest.raises(ValueError, match="requires --project"):
        add_local_source(source)


def test_midi_dispatches_to_existing_importer_and_records_completed_provenance_hash(tmp_path: Path, monkeypatch) -> None:
    source = _file(tmp_path, "bass.mid")
    project = _project(tmp_path)
    output = project / "sources" / "imported" / "bass.json"
    calls: dict[str, object] = {}
    source_sha = sha256_file(source)

    def fake_import(project_path, source_path, **kwargs):
        calls.update(project=project_path, source=source_path, **kwargs)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "provenance": {
                        "source_type": "midi",
                        "source_filename": source.name,
                        "source_sha256": source_sha,
                        "importer": "test",
                        "importer_version": "1",
                    },
                    "tracks": [
                        {
                            "source_track_index": 0,
                            "instrument": "rhythm",
                            "notes": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return output

    monkeypatch.setattr("rocksmith_cdlc_generator.source_workflow.import_project_midi", fake_import)

    result = add_local_source(
        source,
        project=project,
        instrument="rhythm",
        track_index=3,
    )

    assert result.status == "complete"
    assert result.route.action == "import_midi"
    assert result.output_path == str(output.resolve())
    assert calls["project"] == project.resolve()
    assert calls["track_index"] == 3
    assert calls["instrument"] == "rhythm"
    receipt = json.loads(Path(result.intake_receipt_path or "").read_text(encoding="utf-8"))
    assert receipt["source_sha256"] == source_sha


def test_planned_format_is_queued_instead_of_rejected(tmp_path: Path) -> None:
    source = _file(tmp_path, "score.gpx")

    result = add_local_source(source)

    assert result.status == "queued"
    assert result.route.action == "queue_adapter"
    assert result.output_path is None
    assert result.intake_receipt_path is None


def test_planned_format_can_be_queued_into_existing_project_with_receipt(tmp_path: Path) -> None:
    source = _file(tmp_path, "score.gp")
    project = _project(tmp_path)

    result = add_local_source(source, project=project)

    assert result.status == "queued"
    assert result.intake_receipt_path is not None
    assert Path(result.intake_receipt_path).is_file()


def test_receipt_filename_is_bounded_for_long_source_basename(tmp_path: Path) -> None:
    source = _file(tmp_path, f"{'a' * 240}.gp")
    project = _project(tmp_path)

    result = add_local_source(source, project=project)

    receipt_path = Path(result.intake_receipt_path or "")
    assert receipt_path.is_file()
    assert len(receipt_path.name.encode("utf-8")) < 255


def test_unknown_format_is_not_guessed(tmp_path: Path) -> None:
    source = _file(tmp_path, "source.bin")

    with pytest.raises(ValueError, match="not recognized"):
        add_local_source(source)


def test_streaming_reference_class_cannot_enter_local_byte_workflow(tmp_path: Path) -> None:
    source = _file(tmp_path, "song.mp3")

    with pytest.raises(ValueError, match="cannot be added as local source bytes"):
        add_local_source(
            source,
            title="Song",
            rights_class=SourceRightsClass.streaming_reference_only,
        )


def test_psarc_non_bass_route_remains_blocked(tmp_path: Path) -> None:
    source = _file(tmp_path, "custom.psarc")
    project = _project(tmp_path)

    with pytest.raises(ValueError, match="imports Bass arrangements only"):
        add_local_source(source, project=project, instrument="lead")
