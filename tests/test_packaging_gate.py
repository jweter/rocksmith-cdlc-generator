from pathlib import Path

import pytest

from rocksmith_cdlc_generator.packaging_gate import PackagingBlockedError, require_packaging_ready
from tests.test_validation import _write_manifest, _write_valid_artifacts


def test_packaging_gate_allows_valid_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _write_valid_artifacts(project)

    report = require_packaging_ready(project)

    assert report.status == "PASS"
    assert report.can_package is True


def test_packaging_gate_blocks_fail_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)

    with pytest.raises(PackagingBlockedError, match="packaging is blocked"):
        require_packaging_ready(project)
