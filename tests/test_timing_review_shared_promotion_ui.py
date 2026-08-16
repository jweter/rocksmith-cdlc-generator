from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from rocksmith_cdlc_generator import timing_review_ui
from rocksmith_cdlc_generator.timing_review_ui import TimingReviewSongWorkspaceWindow


class _Var:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _Button:
    def __init__(self) -> None:
        self.options: dict[str, str] = {}

    def configure(self, **kwargs) -> None:
        self.options.update(kwargs)


def test_shared_timeline_promotion_uses_shared_authority_not_beat_promotion(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, Path] = {}
    refreshed: list[bool] = []

    monkeypatch.setattr(timing_review_ui.messagebox, "askyesno", lambda *args, **kwargs: True)

    def fake_promote(project: Path) -> Path:
        called["project"] = project
        return project / "analysis" / "shared_timeline.json"

    monkeypatch.setattr(timing_review_ui, "promote_shared_timeline", fake_promote)
    monkeypatch.setattr(
        timing_review_ui,
        "promote_reviewed_timing",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("beat promotion must remain separate")),
    )

    window = SimpleNamespace(
        project=tmp_path,
        timing_gate_var=_Var(),
        refresh=lambda: refreshed.append(True),
    )

    TimingReviewSongWorkspaceWindow._promote_shared_timing(window)

    assert called == {"project": tmp_path}
    assert refreshed == [True]
    assert "Bass, Lead, and Rhythm" in window.timing_gate_var.value


def test_beat_confirmation_explicitly_does_not_promote_shared_timeline(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, Path] = {}

    monkeypatch.setattr(timing_review_ui.messagebox, "askyesno", lambda *args, **kwargs: True)

    review = SimpleNamespace()

    def fake_promote(project: Path):
        called["project"] = project
        return review, project / "analysis" / "reviewed_tempo_map.json"

    monkeypatch.setattr(timing_review_ui, "promote_reviewed_timing", fake_promote)
    monkeypatch.setattr(
        timing_review_ui,
        "promote_shared_timeline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("shared promotion must be explicit")),
    )

    window = SimpleNamespace(
        project=tmp_path,
        reviewed_timing=None,
        timing_review_var=_Var(),
        _refresh_selected_beat_text=lambda: None,
        _refresh_timing_gate_guidance=lambda: None,
        _draw_timeline=lambda: None,
    )

    TimingReviewSongWorkspaceWindow._confirm_beat_edits(window)

    assert called == {"project": tmp_path}
    assert window.reviewed_timing is review
    assert "does not" not in window.timing_review_var.value.lower()
    assert "Shared song timing still requires" in window.timing_review_var.value


def test_shared_timing_guidance_says_individual_beat_locks_are_not_required(monkeypatch, tmp_path: Path) -> None:
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "alignment.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        timing_review_ui,
        "load_current_shared_timeline",
        lambda _project: (_ for _ in ()).throw(FileNotFoundError("not promoted")),
    )

    window = SimpleNamespace(
        project=tmp_path,
        timing_gate_var=_Var(),
        shared_promote_button=_Button(),
    )

    TimingReviewSongWorkspaceWindow._refresh_timing_gate_guidance(window)

    assert window.shared_promote_button.options["state"] == "normal"
    assert window.shared_promote_button.options["text"] == "Promote shared song timing"
    assert "do not need to lock every beat" in window.timing_gate_var.value


def test_current_shared_timeline_disables_duplicate_promotion(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(timing_review_ui, "load_current_shared_timeline", lambda _project: object())

    window = SimpleNamespace(
        project=tmp_path,
        timing_gate_var=_Var(),
        shared_promote_button=_Button(),
    )

    TimingReviewSongWorkspaceWindow._refresh_timing_gate_guidance(window)

    assert window.shared_promote_button.options["state"] == "disabled"
    assert window.shared_promote_button.options["text"] == "Shared timing promoted"
    assert "Run Safe Automatic Steps" in window.timing_gate_var.value
