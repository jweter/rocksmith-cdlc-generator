from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator, model_validator

from .reference_sources import ReferenceSourceRecord, load_reference_sources


_HTTP_URL = TypeAdapter(HttpUrl)


class ReferenceSelection(BaseModel):
    """Explicit human selection of one metadata-only recording/version reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    reference_url: HttpUrl
    display_name: str = Field(min_length=1)
    provider: str | None = None
    version_hint: str | None = None
    confirmation_note: str | None = None
    human_confirmed: bool = True
    selected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("display_name", "provider", "version_hint", "confirmation_note")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("reference selection text must contain a non-whitespace character")
        return stripped

    @model_validator(mode="after")
    def require_explicit_human_confirmation(self) -> "ReferenceSelection":
        if not self.human_confirmed:
            raise ValueError("reference selection must represent explicit human confirmation")
        return self


def _selection_path(project_dir: Path) -> Path:
    return project_dir / "sources" / "reference_selection.json"


def _record_url(record: ReferenceSourceRecord) -> str:
    url = record.descriptor.reference_url
    if url is None:  # ReferenceSourceRecord invariants should make this unreachable.
        raise ValueError("reference record is missing its public URL")
    return str(url)


def select_reference_source(
    project_dir: Path,
    *,
    url: str,
    confirmation_note: str | None = None,
) -> Path:
    """Persist an explicit human choice of one already-registered reference.

    Selection is metadata-only. It does not authorize downloading, ingestion,
    benchmark use, redistribution, or automatic acceptance of musical content.
    """

    project_dir = project_dir.expanduser().resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project_dir}")

    normalized_url = str(_HTTP_URL.validate_python(url))
    records = load_reference_sources(project_dir)
    matches = [record for record in records if _record_url(record) == normalized_url]
    if len(matches) != 1:
        raise ValueError("reference URL must match exactly one registered project reference")

    record = matches[0]
    descriptor_url = record.descriptor.reference_url
    assert descriptor_url is not None
    selection = ReferenceSelection(
        reference_url=descriptor_url,
        display_name=record.descriptor.display_name,
        provider=record.provider,
        version_hint=record.version_hint,
        confirmation_note=confirmation_note,
        human_confirmed=True,
    )

    destination = _selection_path(project_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(selection.model_dump_json(indent=2), encoding="utf-8")
    return destination


def load_reference_selection(project_dir: Path) -> ReferenceSelection | None:
    project_dir = project_dir.expanduser().resolve()
    path = _selection_path(project_dir)
    if not path.is_file():
        return None

    selection = ReferenceSelection.model_validate_json(path.read_text(encoding="utf-8"))
    records = load_reference_sources(project_dir)
    registered_urls = {_record_url(record) for record in records}
    if str(selection.reference_url) not in registered_urls:
        raise ValueError("selected reference no longer matches a registered project reference")
    return selection
