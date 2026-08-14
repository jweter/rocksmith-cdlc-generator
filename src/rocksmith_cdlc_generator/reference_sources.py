from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from pydantic import BaseModel, ConfigDict, Field

from .source_intake import SourceIntakeDescriptor, describe_streaming_reference


class ReferenceSourceRecord(BaseModel):
    """Persisted discovery/version reference that can never represent ingest bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    descriptor: SourceIntakeDescriptor
    provider: str | None = None
    version_hint: str | None = None
    notes: str | None = None
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (normalized or "reference")[:64]


def _record_path(project_dir: Path, *, display_name: str, url: str) -> Path:
    digest = sha256(url.encode("utf-8")).hexdigest()[:16]
    return project_dir / "sources" / "references" / f"{_slug(display_name)}-{digest}.json"


def add_reference_source(
    project_dir: Path,
    *,
    url: str,
    display_name: str,
    provider: str | None = None,
    version_hint: str | None = None,
    notes: str | None = None,
) -> Path:
    """Record a public streaming/video page for discovery and version identification.

    This function intentionally stores URL metadata only. It never downloads,
    converts, probes, or otherwise obtains media bytes from the referenced page.
    """

    project_dir = project_dir.expanduser().resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project_dir}")

    descriptor = describe_streaming_reference(url, display_name=display_name)
    if descriptor.local_bytes_available or descriptor.can_ingest_local_bytes:
        raise ValueError("reference-only sources must never be ingestable as local bytes")

    record = ReferenceSourceRecord(
        descriptor=descriptor,
        provider=provider.strip() if provider and provider.strip() else None,
        version_hint=version_hint.strip() if version_hint and version_hint.strip() else None,
        notes=notes.strip() if notes and notes.strip() else None,
    )
    destination = _record_path(project_dir, display_name=descriptor.display_name, url=str(descriptor.reference_url))
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        existing = ReferenceSourceRecord.model_validate_json(destination.read_text(encoding="utf-8"))
        if str(existing.descriptor.reference_url) == str(record.descriptor.reference_url):
            return destination
        raise FileExistsError(f"Reference record collision: {destination}")

    destination.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return destination


def load_reference_sources(project_dir: Path) -> list[ReferenceSourceRecord]:
    project_dir = project_dir.expanduser().resolve()
    directory = project_dir / "sources" / "references"
    if not directory.is_dir():
        return []
    return [
        ReferenceSourceRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
