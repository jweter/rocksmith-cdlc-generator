from __future__ import annotations

from types import SimpleNamespace

from rocksmith_cdlc_generator.song_workspace_ui import SongWorkspaceWindow


class _Var:
    def __init__(self, value: object = "") -> None:
        self.value = value

    def set(self, value: object) -> None:
        self.value = value


class _Widget:
    """Minimal stand-in for a ttk widget covering only ``.configure(...)`` calls."""

    def __init__(self) -> None:
        self.configured: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.configured.update(kwargs)


def _sources(
    *,
    recording_reviewed: bool,
    score_filename: str | None = None,
    score_sha256: str | None = None,
    score_reviewed: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        recording_sha256="a" * 64,
        recording_reviewed=recording_reviewed,
        score_filename=score_filename,
        score_sha256=score_sha256,
        score_format="toolkit",
        score_track_count=3,
        score_reviewed=score_reviewed,
    )


def _snapshot(sources: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(sources=sources)


def _window() -> SimpleNamespace:
    return SimpleNamespace(
        recording_detail_var=_Var(),
        recording_rights_status_var=_Var(),
        recording_rights_status_label=_Widget(),
        score_detail_var=_Var(),
        score_rights_status_var=_Var(),
        score_rights_status_label=_Widget(),
    )


def test_unreviewed_recording_renders_review_required_status() -> None:
    window = _window()

    SongWorkspaceWindow._refresh_sources(window, _snapshot(_sources(recording_reviewed=False)))

    assert "review required" in window.recording_rights_status_var.value
    assert window.recording_rights_status_label.configured["foreground"] == "#8F82F5"


def test_reviewed_recording_renders_pass_status() -> None:
    window = _window()

    SongWorkspaceWindow._refresh_sources(window, _snapshot(_sources(recording_reviewed=True)))

    assert "Reviewed" in window.recording_rights_status_var.value
    assert window.recording_rights_status_label.configured["foreground"] == "#55D98D"


def test_unregistered_score_renders_informational_status_not_review_required() -> None:
    window = _window()

    SongWorkspaceWindow._refresh_sources(window, _snapshot(_sources(recording_reviewed=True)))

    assert "Not registered" in window.score_rights_status_var.value
    assert window.score_rights_status_label.configured["foreground"] == "#B7C4D6"
    assert window.score_detail_var.value == ""


def test_registered_unreviewed_score_renders_review_required_status() -> None:
    window = _window()
    sources = _sources(
        recording_reviewed=True,
        score_filename="song.toolkit",
        score_sha256="b" * 64,
        score_reviewed=False,
    )

    SongWorkspaceWindow._refresh_sources(window, _snapshot(sources))

    assert "review required" in window.score_rights_status_var.value
    assert window.score_rights_status_label.configured["foreground"] == "#8F82F5"
    assert "song.toolkit" in window.score_detail_var.value


def test_registered_reviewed_score_renders_pass_status() -> None:
    window = _window()
    sources = _sources(
        recording_reviewed=True,
        score_filename="song.toolkit",
        score_sha256="b" * 64,
        score_reviewed=True,
    )

    SongWorkspaceWindow._refresh_sources(window, _snapshot(sources))

    assert "Reviewed" in window.score_rights_status_var.value
    assert window.score_rights_status_label.configured["foreground"] == "#55D98D"
