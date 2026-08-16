from rocksmith_cdlc_generator.guided_desktop import GuidedDesktopApp
from rocksmith_cdlc_generator.project_source_inventory import ProjectSourceInventory, SourceInventoryItem


def _item(
    name: str,
    sha: str,
    *,
    required: bool,
    rights_class: str,
    receipt_path: str | None = None,
) -> SourceInventoryItem:
    return SourceInventoryItem(
        receipt_path=receipt_path or f"sources/intake/{name}.json",
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


def _inventory(*items: SourceInventoryItem) -> ProjectSourceInventory:
    return ProjectSourceInventory(
        project_path="C:/project",
        local_sources=list(items),
        local_audio_sources=0,
        local_symbolic_sources=len(items),
        reference_count=0,
        selected_reference=False,
        reviewed_recording_context=False,
        unresolved_rights_reviews=sum(item.human_rights_review_required for item in items),
        queued_adapter_sources=len(items),
        next_actions=[],
    )


def test_guided_rights_target_uses_inventory_review_required_state() -> None:
    inventory = _inventory(
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
    )

    choices = GuidedDesktopApp.source_rights_choices_from_inventory(inventory)
    target = GuidedDesktopApp.first_unreviewed_source_label(choices)

    assert target is not None
    assert "needs-review.gp5" in target
    assert "already-classified.gp5" not in target
    assert choices[next(label for label in choices if "already-classified.gp5" in label)][1] is False
    assert choices[target][1] is True


def test_duplicate_receipts_preserve_unresolved_rights_state() -> None:
    sha = "c" * 64
    inventory = _inventory(
        _item(
            "same-score.gp5",
            sha,
            required=False,
            rights_class="user_owned_local",
            receipt_path="sources/intake/local.json",
        ),
        _item(
            "same-score.gp5",
            sha,
            required=True,
            rights_class="unknown",
            receipt_path="sources/intake/score-registration.json",
        ),
    )

    choices = GuidedDesktopApp.source_rights_choices_from_inventory(inventory)

    assert len(choices) == 1
    label, choice = next(iter(choices.items()))
    assert "same-score.gp5" in label
    assert choice == (sha, True, "unknown")
    assert GuidedDesktopApp.first_unreviewed_source_label(choices) == label


def test_duplicate_resolved_receipts_remain_resolved() -> None:
    sha = "d" * 64
    inventory = _inventory(
        _item("same-score.gp5", sha, required=False, rights_class="user_owned_local"),
        _item("same-score.gp5", sha, required=False, rights_class="user_owned_local"),
    )

    choices = GuidedDesktopApp.source_rights_choices_from_inventory(inventory)

    assert len(choices) == 1
    assert next(iter(choices.values())) == (sha, False, "user_owned_local")
    assert GuidedDesktopApp.first_unreviewed_source_label(choices) is None


def test_legacy_label_to_hash_helper_remains_compatible() -> None:
    choices = {"recording": "audio-sha", "score": "score-sha"}

    assert GuidedDesktopApp.first_unreviewed_source_label(
        choices,
        {"audio-sha": object()},
    ) == "score"
