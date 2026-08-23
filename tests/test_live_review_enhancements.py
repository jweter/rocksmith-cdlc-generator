from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import live_review_enhancements, validation
from rocksmith_cdlc_generator.human_review_marks import load_human_review_layer
from rocksmith_cdlc_generator.live_review_enhancements import LiveReviewEnhancementMixin
from rocksmith_cdlc_generator.package_generation import current_package_generation


class _FakeNote:
    def __init__(self, event_index: int, start_seconds: float, midi: int, string_index: int, fret: int) -> None:
        self.event_index = event_index
        self.start_seconds = start_seconds
        self.midi = midi
        self.string_index = string_index
        self.fret = fret


class _FakeArrangement:
    def __init__(self, instrument: str) -> None:
        self.instrument = instrument


class _FakeMixinHost:
    """Minimal duck-typed stand-in for the real Tk-based host class.

    ``LiveReviewEnhancementMixin`` methods are plain Python that only touch a handful of
    attributes/methods on ``self``; exercising them directly here avoids needing a real
    Tk widget tree.
    """

    def __init__(self, project: Path, arrangement: str, note: _FakeNote) -> None:
        self.project = project
        self.score_preview = SimpleNamespace(source_sha256="a" * 64)
        self._arrangement = _FakeArrangement(arrangement)
        self._note = note
        self.revalidate_calls: list[str] = []
        self.refresh_calls = 0

    def _selected_note(self):
        return self._note

    def _active_measure_arrangement(self):
        return self._arrangement

    def _revalidate_after_mark_change(self, arrangement: str) -> None:
        self.revalidate_calls.append(arrangement)

    def refresh(self) -> None:
        self.refresh_calls += 1


def _stage_fake_package(project: Path) -> str:
    staging = project / "build" / "staging"
    staging.mkdir(parents=True)
    (staging / "psarc_receipt.json").write_text(json.dumps({"safe_for_manual_installation": True}), encoding="utf-8")
    (project / "build" / "dlcbuilder").mkdir(parents=True)
    return current_package_generation(project)


def test_wrong_mark_invalidates_existing_staged_package(tmp_path: Path) -> None:
    """#3: a `wrong` mark recorded after a package was already staged/registered must
    invalidate that stale staging directory/receipt rather than leaving it reporting
    `safe_for_manual_installation: true` for content the reviewer just rejected."""

    project = tmp_path / "project"
    project.mkdir()
    prior_generation = _stage_fake_package(project)
    host = _FakeMixinHost(project, "lead", _FakeNote(3, 1.25, 52, 1, 4))

    LiveReviewEnhancementMixin._mark_selected(host, "wrong")

    assert not (project / "build" / "staging").exists()
    assert not (project / "build" / "dlcbuilder").exists()
    assert current_package_generation(project) != prior_generation
    layer = load_human_review_layer(project)
    assert layer is not None
    assert layer.marks[0].state == "wrong"
    assert host.revalidate_calls == ["lead"]
    assert host.refresh_calls == 1


def test_questionable_mark_does_not_invalidate_staged_package(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    prior_generation = _stage_fake_package(project)
    host = _FakeMixinHost(project, "lead", _FakeNote(3, 1.25, 52, 1, 4))

    LiveReviewEnhancementMixin._mark_selected(host, "questionable")

    assert (project / "build" / "staging").exists()
    assert (project / "build" / "staging" / "psarc_receipt.json").is_file()
    assert current_package_generation(project) == prior_generation


def test_wrong_mark_on_bass_also_invalidates_staged_package(tmp_path: Path) -> None:
    """#1/#3 together: Bass is no longer exempt from the same wrong-mark safety net."""

    project = tmp_path / "project"
    project.mkdir()
    prior_generation = _stage_fake_package(project)
    host = _FakeMixinHost(project, "bass", _FakeNote(0, 1.0, 40, 0, 12))

    LiveReviewEnhancementMixin._mark_selected(host, "wrong")

    assert not (project / "build" / "staging").exists()
    assert current_package_generation(project) != prior_generation
    assert host.revalidate_calls == ["bass"]


def test_revalidate_after_mark_change_dispatches_bass_to_bass_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1: Bass previously had no revalidation path at all here, so a `wrong` mark never
    reached ``validation.validate_project`` and Bass silently kept passing the packaging
    gate. This confirms the dispatch, not just the guard clause, was fixed."""

    calls: list[str] = []
    monkeypatch.setattr(validation, "validate_project_to_disk", lambda project: calls.append("bass") or Path("x"))

    host = SimpleNamespace(project=tmp_path)
    LiveReviewEnhancementMixin._revalidate_after_mark_change(host, "bass")

    assert calls == ["bass"]


def test_revalidate_after_mark_change_still_ignores_unknown_roles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(validation, "validate_project_to_disk", lambda project: calls.append("bass"))
    host = SimpleNamespace(project=tmp_path)

    LiveReviewEnhancementMixin._revalidate_after_mark_change(host, "vocals")

    assert calls == []
