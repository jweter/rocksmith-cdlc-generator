from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.project_source_inventory import build_project_source_inventory
from rocksmith_cdlc_generator.source_intake import SourceRightsClass
from rocksmith_cdlc_generator.source_rights_review import (
    latest_source_rights_reviews,
    load_source_rights_reviews,
    record_source_rights_review,
)
from rocksmith_cdlc_generator.source_router import route_local_source
from rocksmith_cdlc_generator.source_workflow import SourceIntakeReceipt


SOURCE_SHA = "a" * 64


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def _receipt(project: Path, *, filename: str = "song.flac", source_sha: str = SOURCE_SHA) -> None:
    route = route_local_source(filename)
    receipt = SourceIntakeReceipt(
        descriptor=route.descriptor,
        route_action=route.action,
        route_reason=route.reason,
        source_sha256=source_sha,
        output_relative_path=None,
    )
    directory = project / "sources" / "intake"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "source.json").write_text(receipt.model_dump_json(indent=2), encoding="utf-8")


def test_review_is_append_only_and_latest_review_wins(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _receipt(project)

    first = record_source_rights_review(
        project,
        source_sha256=SOURCE_SHA,
        rights_class=SourceRightsClass.user_owned_local,
        note="Owned DRM-free local copy",
    )
    second = record_source_rights_review(
        project,
        source_sha256=SOURCE_SHA,
        rights_class=SourceRightsClass.licensed_download,
        note="Later confirmed licensed download",
    )

    reviews = load_source_rights_reviews(project)
    assert len(reviews) == 2
    assert first.is_file()
    assert second.is_file()
    assert first != second
    latest_path, latest = latest_source_rights_reviews(project)[SOURCE_SHA]
    assert latest_path == second
    assert latest.rights_class is SourceRightsClass.licensed_download


def test_review_ordering_survives_a_reviewed_at_timestamp_collision(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _receipt(project)

    frozen_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # A uuid suffix that sorts in the *opposite* direction of call order, so that on a
    # reviewed_at collision the filename ordering only comes out right if something
    # other than the (random) uuid suffix carries call order -- proving the fix, not
    # just getting lucky with random bytes.
    reversed_order_uuids = [UUID("f" * 32), UUID("0" * 32)]
    with (
        patch("rocksmith_cdlc_generator.source_rights_review.datetime") as mock_datetime,
        patch(
            "rocksmith_cdlc_generator.source_rights_review.uuid4",
            side_effect=reversed_order_uuids,
        ),
    ):
        mock_datetime.now.return_value = frozen_now
        first = record_source_rights_review(
            project,
            source_sha256=SOURCE_SHA,
            rights_class=SourceRightsClass.user_owned_local,
            note="Owned DRM-free local copy",
        )
        second = record_source_rights_review(
            project,
            source_sha256=SOURCE_SHA,
            rights_class=SourceRightsClass.licensed_download,
            note="Later confirmed licensed download",
        )

    assert first != second
    reviews = load_source_rights_reviews(project)
    assert [review.rights_class for _, review in reviews] == [
        SourceRightsClass.user_owned_local,
        SourceRightsClass.licensed_download,
    ]
    latest_path, latest = latest_source_rights_reviews(project)[SOURCE_SHA]
    assert latest_path == second
    assert latest.rights_class is SourceRightsClass.licensed_download


def test_review_rejects_unknown_project_source_hash(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _receipt(project)

    with pytest.raises(ValueError, match="known local project source"):
        record_source_rights_review(
            project,
            source_sha256="b" * 64,
            rights_class=SourceRightsClass.user_owned_local,
        )


@pytest.mark.parametrize(
    "rights_class",
    [SourceRightsClass.unknown, SourceRightsClass.streaming_reference_only],
)
def test_review_cannot_confirm_unsafe_or_unresolved_classification(
    tmp_path: Path,
    rights_class: SourceRightsClass,
) -> None:
    project = _project(tmp_path)
    _receipt(project)

    with pytest.raises(ValueError):
        record_source_rights_review(
            project,
            source_sha256=SOURCE_SHA,
            rights_class=rights_class,
        )


def test_inventory_uses_review_without_mutating_original_receipt(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _receipt(project)

    before = build_project_source_inventory(project)
    assert before.unresolved_rights_reviews == 1
    assert before.local_sources[0].rights_class == "unknown"

    review_path = record_source_rights_review(
        project,
        source_sha256=SOURCE_SHA,
        rights_class=SourceRightsClass.user_owned_local,
        note="Human confirmed local ownership",
    )
    after = build_project_source_inventory(project)

    assert after.unresolved_rights_reviews == 0
    assert after.local_sources[0].rights_class == "user_owned_local"
    assert after.local_sources[0].rights_review_path == review_path.relative_to(project).as_posix()
    assert after.local_sources[0].rights_reviewed_at is not None

    original = SourceIntakeReceipt.model_validate_json(
        (project / "sources" / "intake" / "source.json").read_text(encoding="utf-8")
    )
    assert original.descriptor.rights_class is SourceRightsClass.unknown


def test_legacy_manifest_audio_can_receive_durable_rights_review(tmp_path: Path) -> None:
    project = tmp_path / "legacy"
    project.mkdir()
    manifest = ProjectManifest(
        project_name="legacy",
        title="Song",
        source_original_path="C:/Music/song.flac",
        source_project_path="source/original/song.flac",
        source_sha256=SOURCE_SHA,
        source_metadata=AudioMetadata(
            duration_seconds=180.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="flac",
            format_name="flac",
        ),
    )
    manifest.save(project)

    before = build_project_source_inventory(project)
    assert before.local_audio_sources == 1
    assert before.unresolved_rights_reviews == 1

    record_source_rights_review(
        project,
        source_sha256=SOURCE_SHA,
        rights_class=SourceRightsClass.user_owned_local,
    )
    after = build_project_source_inventory(project)

    assert after.local_audio_sources == 1
    assert after.unresolved_rights_reviews == 0
    assert after.local_sources[0].receipt_path == "project.json"
    assert after.local_sources[0].rights_class == "user_owned_local"
