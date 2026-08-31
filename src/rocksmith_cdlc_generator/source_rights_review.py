from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import ProjectManifest
from .source_intake import SourceRightsClass
from .source_workflow import SourceIntakeReceipt


class SourceRightsReview(BaseModel):
    """Explicit human review of one immutable local source identity.

    Reviews are append-only and keyed to the source SHA-256 rather than a mutable
    filename. They refine rights/provenance metadata only; they do not make a
    source trusted musical ground truth or authorize redistribution.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source_sha256: str = Field(min_length=64, max_length=64)
    rights_class: SourceRightsClass
    note: str | None = None
    human_confirmed: bool = True
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("source_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("source_sha256 must be a 64-character hexadecimal SHA-256")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("review note must contain a non-whitespace character")
        return stripped

    @model_validator(mode="after")
    def enforce_review_boundary(self) -> "SourceRightsReview":
        if not self.human_confirmed:
            raise ValueError("source rights review must represent explicit human confirmation")
        if self.rights_class is SourceRightsClass.unknown:
            raise ValueError("source rights review cannot confirm an unknown rights class")
        if self.rights_class is SourceRightsClass.streaming_reference_only:
            raise ValueError("streaming-reference-only is not valid for local source bytes")
        return self


def _require_project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _known_source_hashes(project: Path) -> set[str]:
    hashes: set[str] = set()

    try:
        manifest = ProjectManifest.load(project)
    except (ValueError, TypeError):
        manifest = None
    if manifest is not None:
        hashes.add(manifest.source_sha256.lower())

    intake_dir = project / "sources" / "intake"
    if intake_dir.is_dir():
        for path in sorted(intake_dir.glob("*.json")):
            receipt = SourceIntakeReceipt.model_validate_json(path.read_text(encoding="utf-8"))
            hashes.add(receipt.source_sha256.lower())
    return hashes


def _review_dir(project: Path) -> Path:
    return project / "sources" / "intake" / "rights_reviews"


def record_source_rights_review(
    project_dir: Path,
    *,
    source_sha256: str,
    rights_class: SourceRightsClass,
    note: str | None = None,
) -> Path:
    """Append one human-confirmed rights/provenance review for a known local source."""

    project = _require_project(project_dir)
    normalized_sha = source_sha256.strip().lower()
    if normalized_sha not in _known_source_hashes(project):
        raise ValueError("source SHA-256 does not match a known local project source")

    review = SourceRightsReview(
        source_sha256=normalized_sha,
        rights_class=rights_class,
        note=note,
        human_confirmed=True,
    )
    directory = _review_dir(project)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = review.reviewed_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    # A zero-padded sequence number (count of reviews already on disk) breaks ties
    # deterministically by call order when two reviews land in the same microsecond
    # (observed on Windows CI, where the wall clock's resolution can exceed the time
    # between two back-to-back calls). The uuid suffix alone cannot do this: it is
    # unrelated to insertion order, so sorting by filename would pick a "latest"
    # review at random on a timestamp collision.
    sequence = len(list(directory.glob("*.json")))
    destination = directory / f"rights-{normalized_sha[:12]}-{timestamp}-{sequence:06d}-{uuid4().hex[:8]}.json"
    destination.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    return destination


def load_source_rights_reviews(project_dir: Path) -> list[tuple[Path, SourceRightsReview]]:
    """Load every append-only rights review in chronological order."""

    project = _require_project(project_dir)
    directory = _review_dir(project)
    if not directory.is_dir():
        return []

    reviews = [
        (path, SourceRightsReview.model_validate_json(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*.json"))
    ]
    return sorted(reviews, key=lambda item: (item[1].reviewed_at, item[0].name))


def latest_source_rights_reviews(project_dir: Path) -> dict[str, tuple[Path, SourceRightsReview]]:
    """Return the latest explicit human review for each source SHA-256."""

    latest: dict[str, tuple[Path, SourceRightsReview]] = {}
    for path, review in load_source_rights_reviews(project_dir):
        latest[review.source_sha256] = (path, review)
    return latest
