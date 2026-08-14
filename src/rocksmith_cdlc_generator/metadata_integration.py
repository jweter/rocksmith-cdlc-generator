from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .metadata_providers import SelectedMetadata
from .recording_context import load_reviewed_recording_context


@dataclass(frozen=True)
class ResolvedBuildMetadata:
    album_name: str
    year: int
    album_source: str
    year_source: str
    selected_metadata_path: str | None = None
    recording_context_path: str | None = None


def _reviewed_metadata(project_dir: Path) -> tuple[SelectedMetadata | None, Path]:
    context_path = project_dir / "metadata" / "recording_context.json"
    context = load_reviewed_recording_context(project_dir)
    if context is None:
        return None, context_path
    return context.selected_metadata, context_path


def _suggest_album(selected: SelectedMetadata | None) -> str | None:
    if selected is None:
        return None
    releases = [title.strip() for title in selected.candidate.release_titles if title.strip()]
    unique = list(dict.fromkeys(releases))
    if len(unique) == 1:
        return unique[0]
    return None


def _suggest_year(selected: SelectedMetadata | None) -> int | None:
    if selected is None or not selected.candidate.first_release_date:
        return None
    prefix = selected.candidate.first_release_date[:4]
    if not prefix.isdigit():
        return None
    year = int(prefix)
    if 1900 <= year <= 2100:
        return year
    return None


def resolve_build_metadata(
    project_dir: Path,
    *,
    album_name: str | None,
    year: int | None,
) -> ResolvedBuildMetadata:
    """Resolve DLC Builder album/year with explicit values taking precedence.

    Metadata-derived suggestions are accepted only from ``recording_context.json``,
    which snapshots the catalog selection that was paired with an explicitly
    human-confirmed recording/version reference. A later change to ``selected.json``
    cannot silently alter build metadata until the reviewed context is rebuilt.
    """

    project_dir = project_dir.resolve()
    selected, context_path = _reviewed_metadata(project_dir)

    explicit_album = album_name.strip() if album_name is not None else ""
    if explicit_album:
        resolved_album = explicit_album
        album_source = "explicit"
    else:
        suggestion = _suggest_album(selected)
        if suggestion is None:
            if selected is not None and selected.candidate.release_titles:
                raise ValueError(
                    "Album name is ambiguous in reviewed recording context; pass --album explicitly"
                )
            raise ValueError(
                "Album name is required; pass --album or rebuild reviewed recording context with one unambiguous selected release"
            )
        resolved_album = suggestion
        album_source = "reviewed_recording_context"

    if year is not None:
        if year < 1900 or year > 2100:
            raise ValueError("Year must be between 1900 and 2100")
        resolved_year = year
        year_source = "explicit"
    else:
        suggestion_year = _suggest_year(selected)
        if suggestion_year is None:
            raise ValueError(
                "Release year is required; pass --year or rebuild reviewed recording context with a valid selected first-release date"
            )
        resolved_year = suggestion_year
        year_source = "reviewed_recording_context"

    return ResolvedBuildMetadata(
        album_name=resolved_album,
        year=resolved_year,
        album_source=album_source,
        year_source=year_source,
        # The selected metadata used here is embedded in recording_context.json.
        # Never point auditors at mutable metadata/selected.json for snapshot values.
        selected_metadata_path=None,
        recording_context_path=(
            str(context_path.relative_to(project_dir)) if context_path.is_file() else None
        ),
    )
