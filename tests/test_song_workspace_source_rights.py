from __future__ import annotations

from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.project_source_inventory import ProjectSourceInventory, SourceInventoryItem
from rocksmith_cdlc_generator.score_source import ProjectScoreSource
from rocksmith_cdlc_generator.song_workspace import _source_snapshot


def _item(
    sha: str,
    *,
    required: bool,
    rights_class: str,
    route_action: str = "project_audio",
) -> SourceInventoryItem:
    return SourceInventoryItem(
        receipt_path="sources/intake/source.json",
        display_name="song.wav",
        source_format="wav",
        family="audio",
        route_action=route_action,
        rights_class=rights_class,
        adapter_status="supported",
        source_sha256=sha,
        output_relative_path="source/song.wav",
        human_rights_review_required=required,
        parser_pending=False,
    )


def _inventory(*items: SourceInventoryItem) -> ProjectSourceInventory:
    return ProjectSourceInventory(
        project_path="C:/project",
        local_sources=list(items),
        local_audio_sources=len(items),
        local_symbolic_sources=0,
        reference_count=0,
        selected_reference=False,
        reviewed_recording_context=False,
        unresolved_rights_reviews=len(
            {item.source_sha256 for item in items if item.human_rights_review_required}
        ),
        queued_adapter_sources=0,
        next_actions=[],
    )


def _manifest(sha: str) -> ProjectManifest:
    return ProjectManifest(
        project_name="Artist - Song",
        artist="Artist",
        title="Song",
        arrangement_instruments=["bass"],
        source_original_path="C:/source/song.wav",
        source_project_path="source/song.wav",
        source_sha256=sha,
        source_metadata=AudioMetadata(
            duration_seconds=60.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )


def _score(sha: str) -> ProjectScoreSource:
    return ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=sha,
        source_format="gp5",
        imported_relative_path="sources/score/song.gp5",
        tracks=[],
    )


def test_workspace_uses_inventory_resolved_state_without_explicit_review_receipt() -> None:
    sha = "a" * 64
    inventory = _inventory(_item(sha, required=False, rights_class="user_owned_local"))

    state = _source_snapshot(_manifest(sha), None, inventory)

    assert state.recording_reviewed is True


def test_workspace_fails_closed_when_inventory_content_still_requires_review() -> None:
    sha = "b" * 64
    inventory = _inventory(
        _item(sha, required=False, rights_class="user_owned_local"),
        _item(sha, required=True, rights_class="unknown"),
    )

    state = _source_snapshot(_manifest(sha), None, inventory)

    assert state.recording_reviewed is False


def test_workspace_does_not_claim_reviewed_when_source_is_missing_from_inventory() -> None:
    sha = "c" * 64

    state = _source_snapshot(_manifest(sha), None, _inventory())

    assert state.recording_reviewed is False


def test_workspace_score_requires_matching_registration_receipt() -> None:
    recording_sha = "d" * 64
    score_sha = "e" * 64
    inventory = _inventory(
        _item(recording_sha, required=False, rights_class="user_owned_local"),
        _item(
            score_sha,
            required=False,
            rights_class="user_owned_local",
            route_action="queue_adapter",
        ),
    )

    state = _source_snapshot(_manifest(recording_sha), _score(score_sha), inventory)

    assert state.score_reviewed is False


def test_workspace_score_reviews_only_resolved_registration_receipt() -> None:
    recording_sha = "f" * 64
    score_sha = "1" * 64
    inventory = _inventory(
        _item(recording_sha, required=False, rights_class="user_owned_local"),
        _item(
            score_sha,
            required=False,
            rights_class="user_owned_local",
            route_action="register_score_source",
        ),
    )

    state = _source_snapshot(_manifest(recording_sha), _score(score_sha), inventory)

    assert state.score_reviewed is True
