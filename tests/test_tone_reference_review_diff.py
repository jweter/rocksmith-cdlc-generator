from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.tone_reference_review_diff import (
    build_staged_settings_diff,
    render_staged_settings_diff_markdown,
    write_staged_settings_diff_bundle,
)
from rocksmith_cdlc_generator.tone_review import (
    ToneComponentReview,
    ToneReviewArtifact,
    ToneReviewItem,
)


def _artifact(*, device_key: str = "amp_old", gain: float = 0.4) -> ToneReviewArtifact:
    return ToneReviewArtifact(
        artist="Example Artist",
        title="Example Song",
        catalog_sha256="a" * 64,
        bound_plan_sha256="b" * 64,
        tones=[
            ToneReviewItem(
                arrangement="lead",
                label="Lead",
                components=[
                    ToneComponentReview(
                        family="amp",
                        slot="Amp",
                        device_key=device_key,
                        device_name="Old Amp" if device_key == "amp_old" else "Reference Amp",
                        knob_values={"Gain": gain, "Treble": 0.5},
                    )
                ],
            )
        ],
        ready_for_injection=False,
    )


def test_diff_reports_only_changed_settings_without_approval() -> None:
    original = _artifact()
    staged = _artifact(device_key="amp_ref", gain=0.7)

    report = build_staged_settings_diff(original, staged)

    assert len(report.changes) == 1
    change = report.changes[0]
    assert change.original_device_key == "amp_old"
    assert change.staged_device_key == "amp_ref"
    assert [(item.name, item.original, item.staged) for item in change.knob_changes] == [
        ("Gain", 0.4, 0.7)
    ]
    assert report.unchanged_component_count == 0
    assert report.human_review_required is True
    assert report.can_approve is False
    assert report.can_inject is False
    assert original.tones[0].components[0].device_key == "amp_old"


def test_identical_reviews_report_no_changes() -> None:
    original = _artifact()
    staged = _artifact()

    report = build_staged_settings_diff(original, staged)

    assert report.changes == []
    assert report.unchanged_component_count == 1


def test_diff_rejects_different_bound_plan() -> None:
    original = _artifact()
    staged_data = _artifact().model_dump()
    staged_data["bound_plan_sha256"] = "c" * 64
    staged = ToneReviewArtifact.model_validate(staged_data)

    with pytest.raises(ValueError, match="different bound plans"):
        build_staged_settings_diff(original, staged)


def test_diff_rejects_structural_component_change() -> None:
    original = _artifact()
    staged_data = _artifact().model_dump()
    staged_data["tones"][0]["components"][0]["slot"] = "Cabinet"
    staged = ToneReviewArtifact.model_validate(staged_data)

    with pytest.raises(ValueError, match="same components"):
        build_staged_settings_diff(original, staged)


def test_markdown_and_bundle_keep_human_review_boundary(tmp_path) -> None:
    report = build_staged_settings_diff(_artifact(), _artifact(device_key="amp_ref", gain=0.7))

    markdown = render_staged_settings_diff_markdown(report)
    assert "Human approval remains separate" in markdown
    assert "amp_old" in markdown
    assert "amp_ref" in markdown
    assert "`Gain`: 0.4 → 0.7" in markdown
    assert "does not close the injection gate" in markdown

    json_path, markdown_path = write_staged_settings_diff_bundle(report, tmp_path)
    assert json_path.exists()
    assert markdown_path.exists()
    assert '"can_approve": false' in json_path.read_text(encoding="utf-8")
    assert "Review aid only" in markdown_path.read_text(encoding="utf-8")
