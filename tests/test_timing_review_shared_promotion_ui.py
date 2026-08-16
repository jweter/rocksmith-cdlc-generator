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


def _candidate() -> SimpleNamespace:
    return SimpleNamespace(
        anchors=[SimpleNamespace(source_beat_index=0, audio_time_seconds=2.0)],
        confidence=0.94,
        warnings=[],
    )


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
        candidate_shared_timeline=_candidate(),
        timing_gate_var=_Var(),
        refresh=lambda: refreshed.append(True),
    )

    TimingReviewSongWorkspaceWindow._promote_shared_timing(window)

    assert called == {"project": tmp_path}
    assert refreshed == [True]
    assert "Bass, Lead, and Rhythm" in window.timing_gate_var.value


def test_shared_promotion_refuses_when_no_validated_candidate(monkeypatch, tmp_path: Path) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        timing_review_ui.messagebox,
        "showwarning",
        lambda _title, message, **_kwargs: warned.append(message),
    )
    monkeypatch.setattr(
        timing_review_ui,
        "promote_shared_timeline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("invalid candidate must not promote")),
    )

    window = SimpleNamespace(project=tmp_path, candidate_shared_timeline=None)
    TimingReviewSongWorkspaceWindow._promote_shared_timing(window)

    assert warned
    assert "not validated" in warned[0]


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
    assert "Shared song timing still requires" in window.timing_review_var.value


def test_shared_timing_guidance_requires_validated_candidate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        timing_review_ui,
        "load_current_shared_timeline",
        lambda _project: (_ for _ in ()).throw(FileNotFoundError("not promoted")),
    )
    candidate = _candidate()
    monkeypatch.setattr(timing_review_ui, "build_shared_timeline_candidate", lambda _project: candidate)

    window = SimpleNamespace(
        project=tmp_path,
        candidate_shared_timeline=None,
        timing_gate_var=_Var(),
        shared_promote_button=_Button(),
    )

    TimingReviewSongWorkspaceWindow._refresh_timing_gate_guidance(window)

    assert window.candidate_shared_timeline is candidate
    assert window.shared_promote_button.options["state"] == "normal"
    assert window.shared_promote_button.options["text"] == "Promote shared song timing"
    assert "Validated candidate alignment" in window.timing_gate_var.value
    assert "score anchors" in window.timing_gate_var.value


def test_stale_candidate_disables_promotion_and_surfaces_reason(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        timing_review_ui,
        "load_current_shared_timeline",
        lambda _project: (_ for _ in ()).throw(FileNotFoundError("not promoted")),
    )
    monkeypatch.setattr(
        timing_review_ui,
        "build_shared_timeline_candidate",
        lambda _project: (_ for _ in ()).throw(ValueError("current alignment track does not match the confirmed Bass mapping")),
    )

    window = SimpleNamespace(
        project=tmp_path,
        candidate_shared_timeline=_candidate(),
        timing_gate_var=_Var(),
        shared_promote_button=_Button(),
    )

    TimingReviewSongWorkspaceWindow._refresh_timing_gate_guidance(window)

    assert window.candidate_shared_timeline is None
    assert window.shared_promote_button.options["state"] == "disabled"
    assert "current alignment track does not match" in window.timing_gate_var.value


def test_current_shared_timeline_disables_duplicate_promotion(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(timing_review_ui, "load_current_shared_timeline", lambda _project: object())

    window = SimpleNamespace(
        project=tmp_path,
        candidate_shared_timeline=_candidate(),
        timing_gate_var=_Var(),
        shared_promote_button=_Button(),
    )

    TimingReviewSongWorkspaceWindow._refresh_timing_gate_guidance(window)

    assert window.candidate_shared_timeline is None
    assert window.shared_promote_button.options["state"] == "disabled"
    assert window.shared_promote_button.options["text"] == "Shared timing promoted"
    assert "Run Safe Automatic Steps" in window.timing_gate_var.value


def test_nearest_candidate_anchor_text_exposes_score_correspondence() -> None:
    window = SimpleNamespace(
        candidate_shared_timeline=SimpleNamespace(
            anchors=[
                SimpleNamespace(source_beat_index=7, audio_time_seconds=12.5),
                SimpleNamespace(source_beat_index=15, audio_time_seconds=16.5),
            ]
        ),
        _cursor_time=lambda: 12.6,
    )

    text = TimingReviewSongWorkspaceWindow._nearest_candidate_anchor_text(window)

    assert "source beat 8" in text
    assert "12.500s" in text
