from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.reference_sources import (
    ReferenceSourceRecord,
    add_reference_source,
    load_reference_sources,
)
from rocksmith_cdlc_generator.source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def test_public_youtube_reference_is_persisted_without_local_bytes(tmp_path: Path) -> None:
    project = _project(tmp_path)

    output = add_reference_source(
        project,
        url="https://www.youtube.com/watch?v=example123",
        display_name="Artist - Song (Official Audio)",
        provider="YouTube",
        version_hint="official studio version",
    )

    record = ReferenceSourceRecord.model_validate_json(output.read_text(encoding="utf-8"))
    assert record.descriptor.rights_class.value == "streaming_reference_only"
    assert record.descriptor.adapter_status.value == "reference_only"
    assert record.descriptor.local_bytes_available is False
    assert record.descriptor.can_ingest_local_bytes is False
    assert record.provider == "YouTube"
    assert record.version_hint == "official studio version"


def test_reference_record_model_rejects_local_ingest_descriptor() -> None:
    local_descriptor = SourceIntakeDescriptor(
        display_name="Local song",
        source_format=SourceFormat.mp3,
        family=SourceFamily.audio,
        adapter_status=AdapterStatus.supported,
        rights_class=SourceRightsClass.user_owned_local,
        local_bytes_available=True,
    )

    with pytest.raises(ValidationError, match="streaming_reference_only"):
        ReferenceSourceRecord(descriptor=local_descriptor)


def test_loaded_reference_record_cannot_be_edited_into_local_ingest_material(tmp_path: Path) -> None:
    project = _project(tmp_path)
    output = add_reference_source(
        project,
        url="https://www.youtube.com/watch?v=example123",
        display_name="Song",
    )
    payload = output.read_text(encoding="utf-8")
    payload = payload.replace('"streaming_reference_only"', '"user_owned_local"')
    payload = payload.replace('"reference_only"', '"supported"')
    payload = payload.replace('"local_bytes_available": false', '"local_bytes_available": true')
    output.write_text(payload, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_reference_sources(project)


def test_duplicate_url_is_idempotent(tmp_path: Path) -> None:
    project = _project(tmp_path)
    kwargs = {
        "url": "https://youtu.be/example123",
        "display_name": "Song reference",
    }

    first = add_reference_source(project, **kwargs)
    second = add_reference_source(project, **kwargs)

    assert first == second
    assert len(load_reference_sources(project)) == 1


def test_duplicate_url_stays_idempotent_when_display_name_changes(tmp_path: Path) -> None:
    project = _project(tmp_path)
    url = "https://youtu.be/example123"

    first = add_reference_source(project, url=url, display_name="Initial title")
    second = add_reference_source(project, url=url, display_name="Corrected official title")

    assert first == second
    assert len(load_reference_sources(project)) == 1


def test_reference_filename_identity_is_url_based(tmp_path: Path) -> None:
    project = _project(tmp_path)

    output = add_reference_source(
        project,
        url="https://www.youtube.com/watch?v=example123",
        display_name="A title that may later change",
    )

    assert output.name.startswith("reference-")
    assert "title" not in output.name


def test_reference_registry_rejects_private_or_local_hosts(tmp_path: Path) -> None:
    project = _project(tmp_path)

    with pytest.raises(ValidationError, match="public host"):
        add_reference_source(
            project,
            url="http://127.0.0.1/video",
            display_name="Unsafe local URL",
        )


def test_reference_registry_requires_existing_project(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Not a CDLC project"):
        add_reference_source(
            tmp_path / "missing",
            url="https://www.youtube.com/watch?v=example123",
            display_name="Song",
        )


def test_reference_registry_stores_metadata_only(tmp_path: Path) -> None:
    project = _project(tmp_path)
    add_reference_source(
        project,
        url="https://music.youtube.com/watch?v=example123",
        display_name="Song",
        notes="Use only to identify the exact release/remaster.",
    )

    records = load_reference_sources(project)
    assert len(records) == 1
    dumped = records[0].model_dump(mode="json")
    assert "local_bytes_available" in dumped["descriptor"]
    assert dumped["descriptor"]["local_bytes_available"] is False
    assert "audio_path" not in dumped
    assert "download_path" not in dumped
