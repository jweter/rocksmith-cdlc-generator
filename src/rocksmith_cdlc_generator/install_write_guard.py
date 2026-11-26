"""Guard against writes into the live Rocksmith installation (#796 slice 53).

The project must never modify the live Rocksmith install or NoCableLauncher; exports
and tests write only to project-owned locations. This module is the single, pure check a
writer (or a test fixture) calls before touching a path. It fails closed: a path that
cannot be shown to be outside the install is refused.

A path is refused when it is inside a configured protected root (the
``ROCKSMITH_INSTALL_DIR`` environment variable, several roots separated by
``os.pathsep``) or has a path component named exactly ``Rocksmith2014`` (any case). A
sibling such as ``Rocksmith2014-backup`` is a different folder and is not matched by
the component rule.

Both the *resolved* destination (symlinks followed, and ``..`` applied only after the
symlink before it is followed, exactly as the operating system will) and the *lexical*
spelling are checked, and the installation-name rule looks at the path as written as well
as at the resolved destination. So a symlink into the install, ``link/../file`` where
``link`` points into the install, and a ``Rocksmith2014`` name that is itself a symlink to
a differently named folder are all refused.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path

INSTALL_ENV_VAR = "ROCKSMITH_INSTALL_DIR"
_INSTALL_COMPONENT = "rocksmith2014"


class GameInstallWriteError(PermissionError):
    """Raised when a write target is, or cannot be proven not to be, in the game install."""


def _fold(parts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(part.casefold() for part in parts)


def _resolved_parts(path: str | os.PathLike[str]) -> tuple[str, ...]:
    """Case-folded components of where the OS will really write (symlinks followed).

    ``Path.resolve`` follows a symlink *before* applying a following ``..``; collapsing
    ``..`` lexically first (``os.path.abspath``) would check a different destination.
    """

    return _fold(Path(os.fspath(path)).resolve(strict=False).parts)


def _lexical_parts(path: str | os.PathLike[str]) -> tuple[str, ...]:
    """Case-folded components of the path as spelled, made absolute and normalized."""

    return _fold(Path(os.path.abspath(os.fspath(path))).parts)


def _raw_parts(path: str | os.PathLike[str]) -> tuple[str, ...]:
    """Case-folded components exactly as written (no normalization, no resolution)."""

    return _fold(Path(os.fspath(path)).parts)


def default_protected_roots(env: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    """Protected roots from ``ROCKSMITH_INSTALL_DIR``; absent or blank means none."""

    source = os.environ if env is None else env
    raw = source.get(INSTALL_ENV_VAR, "")
    return tuple(Path(item) for item in raw.split(os.pathsep) if item.strip())


def is_inside_protected_root(
    path: str | os.PathLike[str], protected_roots: Iterable[str | os.PathLike[str]]
) -> bool:
    """Whether ``path`` equals or lies under any root, or has a ``Rocksmith2014`` component."""

    path_forms = (_resolved_parts(path), _lexical_parts(path))
    if any(_INSTALL_COMPONENT in parts for parts in (*path_forms, _raw_parts(path))):
        return True
    for root in protected_roots:
        if not os.fspath(root).strip():
            continue
        for root_parts in (_resolved_parts(root), _lexical_parts(root)):
            if any(parts[: len(root_parts)] == root_parts for parts in path_forms):
                return True
    return False


def assert_not_in_game_install(
    path: object,
    protected_roots: Iterable[str | os.PathLike[str]] | None = None,
) -> None:
    """Raise :class:`GameInstallWriteError` unless ``path`` is safely outside the install.

    ``protected_roots=None`` reads :func:`default_protected_roots`. A missing, empty or
    non-path value cannot be shown safe and is refused.
    """

    if not isinstance(path, (str, os.PathLike)) or not os.fspath(path).strip():
        raise GameInstallWriteError(
            "Refusing a write: the target path is missing or invalid."
        )
    roots = (
        default_protected_roots() if protected_roots is None else tuple(protected_roots)
    )
    if is_inside_protected_root(path, roots):
        raise GameInstallWriteError(
            f"Refusing a write into the live Rocksmith installation: {os.fspath(path)}"
        )
