from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.project_source_inventory import build_project_source_inventory
from rocksmith_cdlc_generator.recording_context import ReviewedRecordingContext
from rocksmith_cdlc_generator.reference_selection import ReferenceSelection, select_reference_source
from rocksmith_cdlc_generator.reference_sources import add_reference_source
from rocksmith_cdlc_generator.source_intake import SourceRightsClass
from rocksmith_cdlc_generator.source_router import route_local_source
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def _write_receipt(
    project: Path,
    *,
    filename: str,
    rights_class: SourceRightsClass = SourceRightsClass.unknown,
) -> None:
    route = route_local_source(filename, rights_class=rights_class)
    receipt = SourceIntakeReceipt(
        descriptor=route.descriptor,
        route_action=route.action,
        route_reason=route.reason,
        source_sha256="a" * 64,
        output_relative_path=None,
    )
    directory = project / "sources" / "intake"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{filename}.json").write_text(receipt.model_dump_json(indent=2), encoding="utf-8")


def test_empty_project_reports_concrete_source_and_reference_next_steps(tmp_path: Path) -> None:
    project = _project(tmp_path)

    inventory = build_project_source_inventory(project)

    assert inventory.local_sources == []
    assert inventory.reference_count == 0
    assert inventory.unresolved_rights_reviews == 0
    assert inventory.queued_adapter_sources == 0
    assert any("add-source" in action for action in inventory.next_actions)
    assert any("reference" in action.lower() for action in inventory.next_actions)


def test_inventory_surfaces_rights_review_and_waiting_parser(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write_receipt(project, filename="song.flac")
    _write_receipt(project, filename="score.gpx", rights_class=SourceRightsClass.user_owned_local)

    inventory = build_project_source_inventory(project)

    assert len(inventory.local_sources) == 2
    assert inventory.unresolved_rights_reviews == 1
    assert inventory.queued_adapter_sources == 1
    assert any(item.source_format == "gpx" and item.parser_pending for item in inventory.local_sources)
    assert any("rights/provenance" in action for action in inventory.next_actions)
    assert any("parser adapters" in action for action in inventory.next_actions)


def test_inventory_tracks_reference_selection_and_reviewed_context(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _write_receipt(
        project,
        filename="song.flac",
        rights_class=SourceRightsClass.user_owned_local,
    )
    url = "https://www.youtube.com/watch?v=example123"
    add_reference_source(
        project,
        url=url,
        display_name="Official studio upload",
        provider="YouTube",
        version_hint="album version",
    )

    before_selection = build_project_source_inventory(project)
    assert before_selection.reference_count == 1
    assert before_selection.selected_reference is False
    assert any("select" in action.lower() for action in before_selection.next_actions)

    select_reference_source(project, url=url, confirmation_note="Matches the intended studio version")
    after_selection = build_project_source_inventory(project)
    assert after_selection.selected_reference is True
    assert after_selection.reviewed_recording_context is False
    assert any("recording context" in action.lower() for action in after_selection.next_actions)

    selection = ReferenceSelection(
        reference_url=url,
        display_name="Official studio upload",
        provider="YouTube",
        version_hint="album version",
        confirmation_note="Matches the intended studio version",
    )
    context = ReviewedRecordingContext(reference_selection=selection)
    metadata = project / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "recording_context.json").write_text(context.model_dump_json(indent=2), encoding="utf-8")

    ready = build_project_source_inventory(project)
    assert ready.reviewed_recording_context is True
    assert ready.unresolved_rights_reviews == 0
    assert ready.queued_adapter_sources == 0
    assert any("ready for analysis/alignment" in action for action in ready.next_actions)


def test_inventory_rejects_non_project_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    missing.mkdir()

    try:
        build_project_source_inventory(missing)
    except FileNotFoundError as exc:
        assert "Not a CDLC project" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")
