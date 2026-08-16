from pathlib import Path

import pytest

from rocksmith_cdlc_generator.project_source_inventory import build_project_source_inventory
from rocksmith_cdlc_generator.score_fanout import _require_score_rights_review
from rocksmith_cdlc_generator.score_source import ProjectScoreSource
from rocksmith_cdlc_generator.source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
)
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt
from rocksmith_cdlc_generator.workflow_plan import _score_rights_are_resolved


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def _write_receipt(
    project: Path,
    *,
    name: str,
    digest: str,
    rights_class: SourceRightsClass,
    route_action: str,
) -> None:
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
        route_action=route_action,
        route_reason="rights conflict regression fixture",
        source_sha256=digest,
        output_relative_path="sources/score/original/song.gp5",
    )
    directory = project / "sources" / "intake"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(receipt.model_dump_json(indent=2), encoding="utf-8")


def _score(digest: str) -> ProjectScoreSource:
    return ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path="sources/score/original/song.gp5",
        tracks=[],
        arrangement_mappings=[],
    )


def test_conflicting_resolved_duplicate_receipts_block_authoritative_rights_gate(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    digest = "a" * 64
    _write_receipt(
        project,
        name="score-registration",
        digest=digest,
        rights_class=SourceRightsClass.user_owned_local,
        route_action="register_score_source",
    )
    _write_receipt(
        project,
        name="manual-intake",
        digest=digest,
        rights_class=SourceRightsClass.creative_commons,
        route_action="queue_adapter",
    )

    inventory = build_project_source_inventory(project)
    matching = [item for item in inventory.local_sources if item.source_sha256 == digest]

    assert inventory.unresolved_rights_reviews == 1
    assert len(matching) == 2
    assert all(item.human_rights_review_required for item in matching)
    assert all(item.rights_class == "unknown" for item in matching)
    assert _score_rights_are_resolved(inventory, _score(digest)) is False

    with pytest.raises(ValueError, match="rights/provenance still require human review"):
        _require_score_rights_review(project, _score(digest))


def test_duplicate_receipts_with_same_resolved_class_remain_resolved(tmp_path: Path) -> None:
    project = _project(tmp_path)
    digest = "b" * 64
    for name, route_action in (
        ("score-registration", "register_score_source"),
        ("manual-intake", "queue_adapter"),
    ):
        _write_receipt(
            project,
            name=name,
            digest=digest,
            rights_class=SourceRightsClass.user_owned_local,
            route_action=route_action,
        )

    inventory = build_project_source_inventory(project)
    matching = [item for item in inventory.local_sources if item.source_sha256 == digest]

    assert inventory.unresolved_rights_reviews == 0
    assert len(matching) == 2
    assert all(not item.human_rights_review_required for item in matching)
    assert all(item.rights_class == "user_owned_local" for item in matching)
    assert _score_rights_are_resolved(inventory, _score(digest)) is True
