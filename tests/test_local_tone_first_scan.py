from pathlib import Path

import pytest

from rocksmith_cdlc_generator.local_tone_batch import BatchScanReport
from rocksmith_cdlc_generator.local_tone_first_scan import (
    run_controlled_first_scan,
    validate_first_scan_paths,
)


def _roots(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    rocksmith = tmp_path / "Rocksmith2014"
    dlc = rocksmith / "dlc"
    dlc.mkdir(parents=True)
    workspace = tmp_path / "private" / "workspace"
    library = tmp_path / "private" / "library.json"
    return rocksmith, dlc, workspace, library


def test_preflight_accepts_private_workspace_outside_install(tmp_path: Path) -> None:
    rocksmith, dlc, workspace, library = _roots(tmp_path)
    result = validate_first_scan_paths(
        dlc_root=dlc,
        rocksmith_root=rocksmith,
        workspace_root=workspace,
        library_path=library,
        package_limit=5,
    )
    assert result.package_limit == 5
    assert result.dlc_root == str(dlc.resolve())


def test_preflight_rejects_workspace_inside_live_install(tmp_path: Path) -> None:
    rocksmith, dlc, _, library = _roots(tmp_path)
    with pytest.raises(ValueError, match="workspace"):
        validate_first_scan_paths(
            dlc_root=dlc,
            rocksmith_root=rocksmith,
            workspace_root=rocksmith / "private",
            library_path=library,
            package_limit=5,
        )


def test_preflight_caps_first_scan_size(tmp_path: Path) -> None:
    rocksmith, dlc, workspace, library = _roots(tmp_path)
    with pytest.raises(ValueError, match="between 1 and 25"):
        validate_first_scan_paths(
            dlc_root=dlc,
            rocksmith_root=rocksmith,
            workspace_root=workspace,
            library_path=library,
            package_limit=26,
        )


def test_controlled_scan_passes_limit_and_returns_empty_corpus(tmp_path: Path) -> None:
    rocksmith, dlc, workspace, library = _roots(tmp_path)
    seen: dict[str, object] = {}

    def fake_scan(**kwargs: object) -> BatchScanReport:
        seen.update(kwargs)
        return BatchScanReport(
            dlc_root=str(dlc.resolve()),
            library_path=str(library.resolve()),
            planned_count=0,
            succeeded_count=0,
            failed_count=0,
        )

    report = run_controlled_first_scan(
        dlc_root=dlc,
        rocksmith_root=rocksmith,
        workspace_root=workspace,
        library_path=library,
        source_resolver=lambda _: "unknown",
        package_limit=3,
        scan_fn=fake_scan,
    )
    assert seen["limit"] == 3
    assert report.corpus["tone_count"] == 0
    assert report.corpus["psarc_count"] == 0
