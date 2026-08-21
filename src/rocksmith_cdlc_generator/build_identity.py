from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as package_version
import os
import subprocess

from ._build_metadata import BUILD_SHA, BUILD_TIMESTAMP_UTC, BUILD_VERSION

_PACKAGE_NAME = "rocksmith-cdlc-generator"
_PRODUCT_NAME = "Rocksmith CDLC Generator"


@dataclass(frozen=True)
class BuildIdentity:
    """Immutable identity for one running application build."""

    version: str
    commit_sha: str | None
    built_at_utc: str | None
    packaged: bool

    @property
    def short_sha(self) -> str | None:
        return self.commit_sha[:8] if self.commit_sha else None


def _installed_version() -> str:
    try:
        return package_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return "0+unknown"


def _local_git_sha() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if value else None


@lru_cache(maxsize=1)
def current_build_identity() -> BuildIdentity:
    """Resolve build identity once for this process.

    Packaged builds prefer metadata stamped into the bundle by CI. Development
    checkouts may fall back to installed package metadata, an explicit environment
    SHA, and finally the local Git HEAD.
    """

    packaged_sha = BUILD_SHA.strip() if BUILD_SHA else None
    packaged_version = BUILD_VERSION.strip() if BUILD_VERSION else None
    environment_sha = os.environ.get("ROCKSMITH_CDLC_BUILD_SHA")
    commit_sha = packaged_sha or (environment_sha.strip() if environment_sha else None) or _local_git_sha()
    return BuildIdentity(
        version=packaged_version or _installed_version(),
        commit_sha=commit_sha,
        built_at_utc=BUILD_TIMESTAMP_UTC,
        packaged=packaged_sha is not None and packaged_version is not None,
    )


def format_application_title(identity: BuildIdentity) -> str:
    version_label = f"v{identity.version}" if identity.packaged else f"v{identity.version}-dev"
    if identity.short_sha:
        return f"{_PRODUCT_NAME} {version_label} · {identity.short_sha}"
    return f"{_PRODUCT_NAME} {version_label}"


def format_window_title(context: str | None, identity: BuildIdentity) -> str:
    application = format_application_title(identity)
    return f"{context} — {application}" if context else application


def application_title() -> str:
    return format_application_title(current_build_identity())


def window_title(context: str | None = None) -> str:
    return format_window_title(context, current_build_identity())


def build_info_text(identity: BuildIdentity | None = None) -> str:
    identity = identity or current_build_identity()
    lines = [
        f"Product: {_PRODUCT_NAME}",
        f"Version: {identity.version}",
        f"Commit: {identity.commit_sha or 'unknown'}",
        f"Build type: {'packaged' if identity.packaged else 'development'}",
    ]
    if identity.built_at_utc:
        lines.append(f"Built at (UTC): {identity.built_at_utc}")
    return "\n".join(lines)
