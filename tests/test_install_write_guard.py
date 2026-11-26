from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.install_write_guard import (
    INSTALL_ENV_VAR,
    GameInstallWriteError,
    assert_not_in_game_install,
    default_protected_roots,
    is_inside_protected_root,
)


def test_path_inside_a_protected_root_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    target = root / "dlc" / "song.psarc"

    assert is_inside_protected_root(target, [root]) is True
    with pytest.raises(GameInstallWriteError):
        assert_not_in_game_install(target, [root])


def test_the_root_itself_counts_as_inside(tmp_path: Path) -> None:
    root = tmp_path / "game"
    assert is_inside_protected_root(root, [root]) is True


def test_path_outside_every_root_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "game"
    other = tmp_path / "work" / "export.psarc"

    assert is_inside_protected_root(other, [root]) is False
    assert_not_in_game_install(other, [root])  # does not raise


def test_dotdot_escape_into_the_root_is_caught(tmp_path: Path) -> None:
    root = tmp_path / "game"
    sneaky = tmp_path / "work" / ".." / "game" / "dlc" / "x.psarc"

    assert is_inside_protected_root(sneaky, [root]) is True


def test_dotdot_that_leaves_the_root_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "game"
    leaving = root / ".." / "elsewhere" / "x.psarc"

    assert is_inside_protected_root(leaving, [root]) is False


def test_sibling_folder_with_the_same_prefix_is_not_inside(tmp_path: Path) -> None:
    root = tmp_path / "game"
    sibling = tmp_path / "game-backup" / "x.psarc"

    assert is_inside_protected_root(sibling, [root]) is False


def test_rocksmith2014_component_is_refused_even_without_a_configured_root(
    tmp_path: Path,
) -> None:
    target = tmp_path / "steamapps" / "common" / "Rocksmith2014" / "dlc" / "x.psarc"

    assert is_inside_protected_root(target, []) is True
    with pytest.raises(GameInstallWriteError):
        assert_not_in_game_install(target, [])


def test_rocksmith2014_sibling_name_is_not_matched(tmp_path: Path) -> None:
    assert (
        is_inside_protected_root(tmp_path / "Rocksmith2014-backup" / "x", []) is False
    )
    assert is_inside_protected_root(tmp_path / "MyRocksmith2014" / "x", []) is False


def test_comparison_ignores_case(tmp_path: Path) -> None:
    root = tmp_path / "Game"
    lowered = Path(str(tmp_path).lower()) / "game" / "dlc" / "x.psarc"

    assert is_inside_protected_root(lowered, [root]) is True
    assert is_inside_protected_root(tmp_path / "ROCKSMITH2014" / "x", []) is True


def test_trailing_separator_does_not_change_the_answer(tmp_path: Path) -> None:
    root = tmp_path / "game"
    with_sep = str(root) + os.sep

    assert is_inside_protected_root(root / "x.psarc", [with_sep]) is True
    assert is_inside_protected_root(with_sep + "x.psarc", [root]) is True


def test_blank_roots_are_ignored_not_treated_as_everything(tmp_path: Path) -> None:
    assert is_inside_protected_root(tmp_path / "x.psarc", ["", "   "]) is False


def test_missing_or_invalid_paths_are_refused() -> None:
    for bad in (None, "", "   ", 42, b"bytes-path", ["a"]):
        with pytest.raises(GameInstallWriteError):
            assert_not_in_game_install(bad, [])


def test_env_var_absent_blank_and_present(tmp_path: Path) -> None:
    assert default_protected_roots({}) == ()
    assert default_protected_roots({INSTALL_ENV_VAR: ""}) == ()
    assert default_protected_roots({INSTALL_ENV_VAR: "  "}) == ()

    one = tmp_path / "one"
    two = tmp_path / "two"
    roots = default_protected_roots({INSTALL_ENV_VAR: f"{one}{os.pathsep}{two}"})
    assert roots == (one, two)


def test_default_roots_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "game"
    monkeypatch.setenv(INSTALL_ENV_VAR, str(root))

    with pytest.raises(GameInstallWriteError):
        assert_not_in_game_install(root / "dlc" / "x.psarc")
    assert_not_in_game_install(tmp_path / "work" / "x.psarc")  # outside: no raise


def test_error_names_the_refused_path(tmp_path: Path) -> None:
    root = tmp_path / "game"
    with pytest.raises(GameInstallWriteError, match="live Rocksmith installation"):
        assert_not_in_game_install(root / "x.psarc", [root])


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are not available on this machine")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Win32 collapses '..' lexically before the filesystem sees it; POSIX follows the symlink first",
)
def test_symlink_followed_by_dotdot_is_checked_where_the_os_will_write(
    tmp_path: Path,
) -> None:
    # work/link -> game/subdir, so work/link/../song.psarc really writes game/song.psarc.
    game = tmp_path / "game"
    (game / "subdir").mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    _symlink_or_skip(work / "link", game / "subdir")
    sneaky = str(work / "link") + os.sep + ".." + os.sep + "song.psarc"

    assert is_inside_protected_root(sneaky, [game]) is True
    with pytest.raises(GameInstallWriteError):
        assert_not_in_game_install(sneaky, [game])


def test_symlink_into_the_install_is_refused(tmp_path: Path) -> None:
    game = tmp_path / "game"
    game.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    _symlink_or_skip(work / "alias", game)

    assert is_inside_protected_root(work / "alias" / "song.psarc", [game]) is True


def test_rocksmith2014_symlinked_to_a_differently_named_folder_is_still_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = tmp_path / "library"
    library.mkdir()
    _symlink_or_skip(tmp_path / "Rocksmith2014", library)
    monkeypatch.chdir(tmp_path)

    assert is_inside_protected_root("Rocksmith2014/song.psarc", []) is True
    with pytest.raises(GameInstallWriteError):
        assert_not_in_game_install("Rocksmith2014/song.psarc", [])


def test_a_symlink_that_leads_outside_the_install_is_not_blocked_by_name_alone(
    tmp_path: Path,
) -> None:
    game = tmp_path / "game"
    game.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _symlink_or_skip(game / "out", elsewhere)

    # Resolved destination is outside, but the lexical spelling is inside the root:
    # the guard fails closed and refuses it.
    assert is_inside_protected_root(game / "out" / "x.psarc", [game]) is True
    assert is_inside_protected_root(elsewhere / "x.psarc", [game]) is False
