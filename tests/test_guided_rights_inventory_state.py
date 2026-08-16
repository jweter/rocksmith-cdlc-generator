from rocksmith_cdlc_generator.guided_desktop import GuidedDesktopApp
from rocksmith_cdlc_generator.project_source_inventory import ProjectSourceInventory, SourceInventoryItem


def _item(name: str, sha: str, *, required: bool, rights_class: str) -> SourceInventoryItem:
    return SourceInventoryItem(
        receipt_path=f"sources/intake/{name}.json",
        display_name=name,
        source_format="gp5",
        family="notation",
        route_action="queue_adapter",
        rights_class=rights_class,
        adapter_status="planned",
        source_sha256=sha,
        human_rights_review_required=required,
        parser_pending=True,
    )


def test_guided_rights_target_uses_inventory_review_required_state() -> None:
    inventory = ProjectSourceInventory(
        project_path="C:/project",
        local_sources=[
            _item(
                "already-classified.gp5",
                "a" * 64,
                required=False,
                rights_class="user_owned_local",
            ),
            _item(
                "needs-review.gp5",
                "b" * 64,
                required=True,
                rights_class="unknown",
            ),
        ],
        local_audio_sources=0,
        local_symbolic_sources=2,
        reference_count=0,
        selected_reference=False,
        reviewed_recording_context=False,
        unresolved_rights_reviews=1,
        queued_adapter_sources=2,
        next_actions=[],
    )

    choices = GuidedDesktopApp.source_rights_choices_from_inventory(inventory)
    target = GuidedDesktopApp.first_unreviewed_source_label(choices)

    assert target is not None
    assert "needs-review.gp5" in target
    assert "already-classified.gp5" not in target
    assert choices[next(label for label in choices if "already-classified.gp5" in label)][1] is False
    assert choices[target][1] is True


def test_legacy_label_to_hash_helper_remains_compatible() -> None:
    choices = {"recording": "audio-sha", "score": "score-sha"}

    assert GuidedDesktopApp.first_unreviewed_source_label(
        choices,
        {"audio-sha": object()},
    ) == "score"
