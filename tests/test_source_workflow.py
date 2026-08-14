from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_audio_source_creates_project_and_persists_intake_receipt(tmp_path: Path, monkeypatch) -> None:
    source = _file(tmp_path, "song.flac")
    created = tmp_path / "projects" / "song"
    created.mkdir(parents=True)
    calls: dict[str, object] = {}

    def fake_create_project(**kwargs):
        calls.update(kwargs)
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
    assert receipt["descriptor"]["rights_class"] == "user_owned_local"
    assert receipt["descriptor"]["source_format"] == "flac"
    assert receipt["source_sha256"]


def test_unknown_rights_remain_reviewable_without_blocking_local_audio(tmp_path: Path, monkeypatch) -> None:
    source = _file(tmp_path, "song.mp3")
    created = tmp_path / "project"
    created.mkdir()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.source_workflow.create_project",
        lambda **kwargs: created,
    )

    result = add_local_source(source, title="Song")

    assert result.status == "complete"
    assert result.human_rights_review_required is True
    assert result.intake_receipt_path is not None


def test_symbolic_source_requires_existing_project(tmp_path: Path) -> None:
    source = _file(tmp_path, "bass.mid")

    with pytest.raises(ValueError, match="requires --project"):
        add_local_source(source)


def test_midi_dispatches_to_existing_importer_and_records_receipt(tmp_path: Path, monkeypatch) -> None:
    source = _file(tmp_path, "bass.mid")
    project = _project(tmp_path)
    output = project / "sources" / "imported" / "bass.json"
    calls: dict[str, object] = {}

    def fake_import(project_path, source_path, **kwargs):
        calls.update(project=project_path, source=source_path, **kwargs)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}", encoding="utf-8")
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
    assert result.intake_receipt_path is not None


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
