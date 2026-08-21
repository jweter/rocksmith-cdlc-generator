from types import SimpleNamespace

import rocksmith_cdlc_generator.build_identity as build_identity
from rocksmith_cdlc_generator.build_identity import (
    BuildIdentity,
    _local_git_sha,
    build_info_text,
    format_application_title,
    format_window_title,
)


def test_packaged_title_includes_version_and_short_commit() -> None:
    identity = BuildIdentity(
        version="1.2.3",
        commit_sha="0123456789abcdef",
        built_at_utc="2026-08-21T20:00:00Z",
        packaged=True,
    )

    assert format_application_title(identity) == "Rocksmith CDLC Generator v1.2.3 · 01234567"
    assert format_window_title("Song Workspace", identity) == (
        "Song Workspace — Rocksmith CDLC Generator v1.2.3 · 01234567"
    )


def test_development_title_is_visibly_distinct() -> None:
    identity = BuildIdentity(
        version="0.1.0",
        commit_sha="fedcba9876543210",
        built_at_utc=None,
        packaged=False,
    )

    assert format_application_title(identity) == "Rocksmith CDLC Generator v0.1.0-dev · fedcba98"


def test_build_info_preserves_full_provenance() -> None:
    identity = BuildIdentity(
        version="1.2.3",
        commit_sha="0123456789abcdef",
        built_at_utc="2026-08-21T20:00:00Z",
        packaged=True,
    )

    text = build_info_text(identity)

    assert "Version: 1.2.3" in text
    assert "Commit: 0123456789abcdef" in text
    assert "Build type: packaged" in text
    assert "Built at (UTC): 2026-08-21T20:00:00Z" in text


def test_local_git_sha_does_not_probe_without_checkout_marker(tmp_path, monkeypatch) -> None:
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("git should not be invoked outside the source checkout")

    monkeypatch.setattr(build_identity.subprocess, "run", fake_run)

    assert _local_git_sha(tmp_path) is None
    assert called is False


def test_local_git_sha_rejects_unrelated_repository_root(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    unrelated = tmp_path / "other-repository"
    commit_sha = "a" * 40

    monkeypatch.setattr(
        build_identity.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=f"{unrelated}\n{commit_sha}\n"),
    )

    assert _local_git_sha(tmp_path) is None


def test_local_git_sha_accepts_exact_source_checkout(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    commit_sha = "b" * 40

    def fake_run(command, **kwargs):
        assert command[:3] == ["git", "-C", str(tmp_path.resolve())]
        return SimpleNamespace(stdout=f"{tmp_path.resolve()}\n{commit_sha}\n")

    monkeypatch.setattr(build_identity.subprocess, "run", fake_run)

    assert _local_git_sha(tmp_path) == commit_sha
