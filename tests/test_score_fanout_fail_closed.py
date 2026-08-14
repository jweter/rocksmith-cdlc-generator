from pathlib import Path

import pytest

from rocksmith_cdlc_generator.score_fanout import _remove_stale_dlcbuilder_state


def test_stale_dlcbuilder_removal_failure_is_not_suppressed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    staging = project / "build" / "dlcbuilder"
    staging.mkdir(parents=True)
    (staging / "song.rs2dlc").write_text("stale", encoding="utf-8")

    def fail_remove(path: Path) -> None:
        raise PermissionError("file is in use")

    monkeypatch.setattr("rocksmith_cdlc_generator.score_fanout.shutil.rmtree", fail_remove)

    with pytest.raises(PermissionError, match="file is in use"):
        _remove_stale_dlcbuilder_state(project)

    assert staging.exists()


def test_silent_incomplete_removal_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    staging = project / "build" / "dlcbuilder"
    staging.mkdir(parents=True)
    (staging / "song.rs2dlc").write_text("stale", encoding="utf-8")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_fanout.shutil.rmtree",
        lambda path: None,
    )

    with pytest.raises(OSError, match="refusing to publish"):
        _remove_stale_dlcbuilder_state(project)

    assert staging.exists()
