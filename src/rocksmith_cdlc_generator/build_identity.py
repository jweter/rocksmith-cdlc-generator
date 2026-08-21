from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
import os
import subprocess

from ._build_metadata import BUILD_SHA, BUILD_TIMESTAMP_UTC

_PACKAGE_NAME = "rocksmith-cdlc-generator"
_PRODUCT_NAME = "Rocksmith CDLC Generator"


@dataclass(frozen=True)
class BuildIdentity:
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


def current_build_identity() -> BuildIdentity:
    """Return deterministic packaged identity, with a developer-checkout fallback."""

    packaged_sha = BUILD_SHA.strip() if BUILD_SHA else None
    environment_sha = os.environ.get("ROCKSMITH_CDLC_BUILD_SHA") or os.environ.get("GITHUB_SHA")
    commit_sha = packaged_sha or (environment_sha.strip() if environment_sha else None) or _local_git_sha()
    return BuildIdentity(
        version=_installed_version(),
        commit_sha=commit_sha,
        built_at_utc=BUILD_TIMESTAMP_UTC,
        packaged=packaged_sha is not None,
    )


def format_application_title(identity: BuildIdentity) -> str:
    version_label = f"v{identity.version}" if identity.packaged else f"v{identity.version}-dev"
    if identity.short_sha:
        return f"{_PRODUCT_NAME} {version_label} · {identity.short_sha}"
    return f"{_PRODUCT_NAME} {version_label}"


def application_title() -> str:
    return format_application_title(current_build_identity())


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
