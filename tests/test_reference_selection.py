from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.reference_selection import (
    ReferenceSelection,
    load_reference_selection,
    select_reference_source,
)
from rocksmith_cdlc_generator.reference_sources import add_reference_source, load_reference_sources


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def test_select_registered_reference_persists_human_confirmation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    url = "https://www.youtube.com/watch?v=abc123"
    add_reference_source(
        project,
        url=url,
        display_name="Official studio upload",
        provider="YouTube",
        version_hint="2011 remaster",
    )

    path = select_reference_source(
        project,
        url=url,
        confirmation_note="Matches the album version I intend to chart.",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path == project / "sources" / "reference_selection.json"
    assert payload["human_confirmed"] is True
    assert payload["reference_url"] == url
    assert payload["provider"] == "YouTube"
    assert payload["version_hint"] == "2011 remaster"
    assert "album version" in payload["confirmation_note"]
    assert len(load_reference_sources(project)) == 1


def test_select_normalizes_url_identity_like_registry(tmp_path: Path) -> None:
    project = _project(tmp_path)
    add_reference_source(
        project,
        url="https://example.com",
        display_name="Official reference",
    )

    path = select_reference_source(project, url="https://example.com")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["reference_url"] == "https://example.com/"


def test_select_requires_exact_registered_reference(tmp_path: Path) -> None:
    project = _project(tmp_path)

    with pytest.raises(ValueError, match="exactly one registered"):
        select_reference_source(
            project,
            url="https://www.youtube.com/watch?v=missing",
        )


def test_loading_selection_fails_if_registered_reference_was_removed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    url = "https://www.youtube.com/watch?v=abc123"
    record_path = add_reference_source(
        project,
        url=url,
        display_name="Official upload",
    )
    select_reference_source(project, url=url)
    record_path.unlink()

    with pytest.raises(ValueError, match="no longer matches"):
        load_reference_selection(project)


def test_reference_selection_cannot_represent_unconfirmed_choice() -> None:
    with pytest.raises(ValidationError, match="explicit human confirmation"):
        ReferenceSelection(
            reference_url="https://www.youtube.com/watch?v=abc123",
            display_name="Official upload",
            human_confirmed=False,
        )
