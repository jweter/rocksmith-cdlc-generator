from __future__ import annotations

import json

import pytest

from rocksmith_cdlc_generator.package_generation import (
    bump_package_generation,
    current_package_generation,
    invalidate_package_state,
    require_package_generation,
)


def test_package_generation_defaults_then_advances(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    initial = current_package_generation(project)
    assert initial == "0" * 64

    first = bump_package_generation(project)
    second = bump_package_generation(project)

    assert len(first) == 64
    assert len(second) == 64
    assert first != initial
    assert second != first
    assert current_package_generation(project) == second


def test_invalidate_package_state_advances_before_removing_package_dirs(tmp_path):
    project = tmp_path / "project"
    dlcbuilder = project / "build" / "dlcbuilder"
    staging = project / "build" / "staging"
    dlcbuilder.mkdir(parents=True)
    staging.mkdir(parents=True)
    (dlcbuilder / "song.rs2dlc").write_text("{}", encoding="utf-8")
    (staging / "psarc_receipt.json").write_text("stale", encoding="utf-8")

    prior = current_package_generation(project)
    current = invalidate_package_state(project)

    assert current != prior
    assert current_package_generation(project) == current
    assert not dlcbuilder.exists()
    assert not staging.exists()
    marker = json.loads((project / "build" / "package_generation.json").read_text(encoding="utf-8"))
    assert marker["token"] == current


def test_require_package_generation_fails_closed_after_change(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    expected = bump_package_generation(project)
    bump_package_generation(project)

    with pytest.raises(ValueError, match="stale"):
        require_package_generation(project, expected)
