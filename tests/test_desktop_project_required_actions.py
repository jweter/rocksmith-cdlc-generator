"""Regression coverage for project-required desktop actions (#304/#305).

Visible controls must not silently do nothing when no project is open. The base
shell uses one helper so every project-bound action gives the same owned,
actionable recovery notice.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from rocksmith_cdlc_generator import desktop_app


class _FakeApp:
    def __init__(self, project: Path | None) -> None:
        self.project = project


def test_require_project_returns_the_current_project_without_a_dialog(monkeypatch, tmp_path: Path) -> None:
    app = _FakeApp(tmp_path)
    calls: list[tuple] = []
    monkeypatch.setattr(desktop_app.messagebox, "showinfo", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = desktop_app.DesktopApp._require_project(app)

    assert result == tmp_path
    assert calls == []


def test_require_project_explains_the_recovery_action_in_an_owned_dialog(monkeypatch) -> None:
    app = _FakeApp(None)
    calls: list[tuple] = []
    monkeypatch.setattr(desktop_app.messagebox, "showinfo", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = desktop_app.DesktopApp._require_project(app)

    assert result is None
    assert calls == [
        (
            (desktop_app.APP_TITLE, "Open or create a project first."),
            {"parent": app},
        )
    ]


def test_visible_project_bound_actions_share_the_same_guard() -> None:
    guarded_methods = (
        desktop_app.DesktopApp.open_project_folder,
        desktop_app.DesktopApp.register_score_dialog,
        desktop_app.DesktopApp.confirm_mapping,
        desktop_app.DesktopApp.record_rights_review,
        desktop_app.DesktopApp.run_automatic_steps,
    )

    for method in guarded_methods:
        source = inspect.getsource(method)
        assert "self._require_project()" in source, method.__name__
