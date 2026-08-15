from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from rocksmith_cdlc_generator import shared_guitar


def test_shared_guitar_build_holds_score_transaction_for_full_inner_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    events: list[str] = []

    @contextmanager
    def transaction(selected_project: Path):
        assert selected_project == project.resolve()
        events.append("lock-enter")
        try:
            yield selected_project / "sources" / "score" / "source.json"
        finally:
            events.append("lock-exit")

    def inner(selected_project: Path, *, arrangement: str) -> Path:
        assert selected_project == project.resolve()
        assert arrangement == "lead"
        events.append("inner-build")
        assert events == ["lock-enter", "inner-build"]
        return selected_project / "charts" / "lead_source.json"

    monkeypatch.setattr(shared_guitar, "score_mapping_transaction", transaction)
    monkeypatch.setattr(shared_guitar, "_build_project_shared_guitar_chart_locked", inner)

    result = shared_guitar.build_project_shared_guitar_chart(project, arrangement="lead")

    assert result == project.resolve() / "charts" / "lead_source.json"
    assert events == ["lock-enter", "inner-build", "lock-exit"]


def test_shared_guitar_transaction_is_released_when_build_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    events: list[str] = []

    @contextmanager
    def transaction(_selected_project: Path):
        events.append("lock-enter")
        try:
            yield project / "sources" / "score" / "source.json"
        finally:
            events.append("lock-exit")

    def fail(_selected_project: Path, *, arrangement: str) -> Path:
        assert arrangement == "rhythm"
        events.append("inner-fail")
        raise ValueError("simulated chart failure")

    monkeypatch.setattr(shared_guitar, "score_mapping_transaction", transaction)
    monkeypatch.setattr(shared_guitar, "_build_project_shared_guitar_chart_locked", fail)

    with pytest.raises(ValueError, match="simulated chart failure"):
        shared_guitar.build_project_shared_guitar_chart(project, arrangement="rhythm")

    assert events == ["lock-enter", "inner-fail", "lock-exit"]
