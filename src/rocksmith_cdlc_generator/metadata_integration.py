from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .metadata_providers import SelectedMetadata


@dataclass(frozen=True)
class ResolvedBuildMetadata:
    album_name: str
    year: int
    album_source: str
    year_source: str
    selected_metadata_path: str | None = None


def _selected_metadata(project_dir: Path) -> tuple[SelectedMetadata | None, Path]:
    path = project_dir / "metadata" / "selected.json"
    if not path.is_file():
        return None, path
    selected = SelectedMetadata.model_validate_json(path.read_text(encoding="utf-8"))
    return selected, path


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

    MusicBrainz-derived values are considered only after a candidate has been
    explicitly selected into ``metadata/selected.json``. Ambiguous release
    titles are never guessed.
    """

    project_dir = project_dir.resolve()
    selected, selected_path = _selected_metadata(project_dir)

    explicit_album = album_name.strip() if album_name is not None else ""
    if explicit_album:
        resolved_album = explicit_album
        album_source = "explicit"
    else:
        suggestion = _suggest_album(selected)
        if suggestion is None:
            if selected is not None and selected.candidate.release_titles:
                raise ValueError(
                    "Album name is ambiguous in selected metadata; pass --album explicitly"
                )
            raise ValueError(
                "Album name is required; pass --album or select metadata with one unambiguous release title"
            )
        resolved_album = suggestion
        album_source = "selected_metadata"

    if year is not None:
        if year < 1900 or year > 2100:
            raise ValueError("Year must be between 1900 and 2100")
        resolved_year = year
        year_source = "explicit"
    else:
        suggestion_year = _suggest_year(selected)
        if suggestion_year is None:
            raise ValueError(
                "Release year is required; pass --year or select metadata with a valid first-release date"
            )
        resolved_year = suggestion_year
        year_source = "selected_metadata"

    return ResolvedBuildMetadata(
        album_name=resolved_album,
        year=resolved_year,
        album_source=album_source,
        year_source=year_source,
        selected_metadata_path=(
            str(selected_path.relative_to(project_dir)) if selected is not None else None
        ),
    )
