from pathlib import Path

import pytest

from rocksmith_cdlc_generator.package_generation import current_package_generation
from rocksmith_cdlc_generator.tone_regions import (
    ArrangementToneRegions,
    ProjectToneRegions,
    ToneRegion,
    confirm_tone_regions,
    load_tone_regions,
)


def _arrangements(*, lead_label: str = "Lead Clean") -> tuple[ArrangementToneRegions, ...]:
    return (
        ArrangementToneRegions(arrangement="bass", default_tone="Bass Drive"),
        ArrangementToneRegions(
            arrangement="lead",
            default_tone=lead_label,
            regions=(
                ToneRegion(start_seconds=12.5, tone_label="Lead Drive"),
                ToneRegion(start_seconds=48.0, tone_label="Lead Solo"),
            ),
        ),
        ArrangementToneRegions(arrangement="rhythm", default_tone="Rhythm Crunch"),
    )


def test_confirm_tone_regions_persists_and_invalidates_package_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    stale_dlcbuilder = project / "build" / "dlcbuilder"
    stale_staging = project / "build" / "staging"
    stale_dlcbuilder.mkdir(parents=True)
    stale_staging.mkdir(parents=True)
    (stale_dlcbuilder / "old.txt").write_text("stale", encoding="utf-8")
    (stale_staging / "old.psarc").write_text("stale", encoding="utf-8")

    before = current_package_generation(project)
    confirmed = confirm_tone_regions(project, arrangements=_arrangements())
    after = current_package_generation(project)

    assert after != before
    assert not stale_dlcbuilder.exists()
    assert not stale_staging.exists()
    assert load_tone_regions(project) == confirmed
    assert confirmed.arrangements[1].regions[1].tone_label == "Lead Solo"


def test_identical_reconfirmation_is_a_no_op(tmp_path: Path) -> None:
    project = tmp_path / "project"
    first = confirm_tone_regions(project, arrangements=_arrangements())
    first_generation = current_package_generation(project)

    second = confirm_tone_regions(project, arrangements=_arrangements())

    assert second == first
    assert current_package_generation(project) == first_generation


def test_changed_tone_authority_advances_generation(tmp_path: Path) -> None:
    project = tmp_path / "project"
    confirm_tone_regions(project, arrangements=_arrangements())
    first_generation = current_package_generation(project)

    confirm_tone_regions(project, arrangements=_arrangements(lead_label="Lead Sparkle"))

    assert current_package_generation(project) != first_generation


def test_tone_regions_require_strict_time_order() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        ArrangementToneRegions(
            arrangement="lead",
            default_tone="Lead Clean",
            regions=(
                ToneRegion(start_seconds=10.0, tone_label="A"),
                ToneRegion(start_seconds=10.0, tone_label="B"),
            ),
        )


def test_project_tone_authority_requires_all_three_arrangements() -> None:
    with pytest.raises(ValueError, match="bass, lead, and rhythm"):
        ProjectToneRegions(
            arrangements=(ArrangementToneRegions(arrangement="bass", default_tone="Bass"),)
        )
