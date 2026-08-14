from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .source_intake import (
    AdapterStatus,
    SourceIntakeDescriptor,
    SourceRightsClass,
    describe_streaming_reference,
)


class ReferenceSourceRecord(BaseModel):
    """Persisted discovery/version reference that can never represent ingest bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    descriptor: SourceIntakeDescriptor
    provider: str | None = None
    version_hint: str | None = None
    notes: str | None = None
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def enforce_reference_only_descriptor(self) -> "ReferenceSourceRecord":
        descriptor = self.descriptor
        if descriptor.rights_class is not SourceRightsClass.streaming_reference_only:
            raise ValueError("reference records require streaming_reference_only rights class")
        if descriptor.adapter_status is not AdapterStatus.reference_only:
            raise ValueError("reference records require reference_only adapter status")
        if descriptor.local_bytes_available or descriptor.can_ingest_local_bytes:
            raise ValueError("reference records cannot represent local ingest bytes")
        if descriptor.reference_url is None:
            raise ValueError("reference records require a public reference URL")
        return self


def _normalized_url(record_or_descriptor: ReferenceSourceRecord | SourceIntakeDescriptor) -> str:
    descriptor = (
        record_or_descriptor.descriptor
        if isinstance(record_or_descriptor, ReferenceSourceRecord)
        else record_or_descriptor
    )
    if descriptor.reference_url is None:  # model invariants should make this unreachable.
        raise ValueError("reference URL is required")
    return str(descriptor.reference_url)


def _record_path(project_dir: Path, *, normalized_url: str) -> Path:
    digest = sha256(normalized_url.encode("utf-8")).hexdigest()[:24]
    return project_dir / "sources" / "references" / f"reference-{digest}.json"


def _find_existing_reference(project_dir: Path, *, normalized_url: str) -> Path | None:
    """Find a matching URL, including records written by the pre-canonical filename scheme."""

    directory = project_dir / "sources" / "references"
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.json")):
        existing = ReferenceSourceRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if _normalized_url(existing) == normalized_url:
            return path
    return None


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
    record = ReferenceSourceRecord(
        descriptor=descriptor,
        provider=provider.strip() if provider and provider.strip() else None,
        version_hint=version_hint.strip() if version_hint and version_hint.strip() else None,
        notes=notes.strip() if notes and notes.strip() else None,
    )
    normalized_url = _normalized_url(record)

    existing_path = _find_existing_reference(project_dir, normalized_url=normalized_url)
    if existing_path is not None:
        return existing_path

    destination = _record_path(project_dir, normalized_url=normalized_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = ReferenceSourceRecord.model_validate_json(destination.read_text(encoding="utf-8"))
        if _normalized_url(existing) == normalized_url:
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
