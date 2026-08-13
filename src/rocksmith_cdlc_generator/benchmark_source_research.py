from __future__ import annotations

from datetime import date
import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


StructuredReferenceFinding = Literal[
    "official_commercial_guitar_pro",
    "community_guitar_pro",
    "other_structured_notation",
    "no_adequate_source_found",
    "not_checked",
]

_FOUND_REFERENCE_KINDS = {
    "official_commercial_guitar_pro",
    "community_guitar_pro",
    "other_structured_notation",
}
_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_SPECIAL_USE_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".invalid",
    ".test",
    ".example",
    ".home.arpa",
)


class BenchmarkSourceResearchRecord(BaseModel):
    """Redistributable metadata from structured-reference source research.

    This record is intentionally pre-acquisition. It records what was found in
    lawful source research without storing source bytes, local paths, or making
    a human acceptance decision for benchmark ground truth.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    benchmark_id: str = Field(pattern=r"^BMARK-[0-9]{3}$")
    finding: StructuredReferenceFinding
    checked_on: date
    evidence_note: str = Field(min_length=1)
    source_page_url: HttpUrl | None = None
    source_title: str | None = None

    @field_validator("evidence_note", "source_title")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("research metadata text must contain a non-whitespace character")
        return stripped

    @field_validator("source_page_url")
    @classmethod
    def require_public_source_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is None:
            return None
        if value.username is not None or value.password is not None:
            raise ValueError("source_page_url must not contain embedded user information")

        host = value.host
        if host is None:
            raise ValueError("source_page_url must use a public host")

        address_host = host[1:-1] if host.startswith("[") and host.endswith("]") else host
        try:
            address = ipaddress.ip_address(address_host)
        except ValueError:
            dns_host = host.rstrip(".").lower()
            labels = dns_host.split(".")
            if (
                len(labels) < 2
                or dns_host == "localhost"
                or dns_host.endswith(_SPECIAL_USE_SUFFIXES)
                or any(not _DNS_LABEL.fullmatch(label) for label in labels)
            ):
                raise ValueError("source_page_url must use a public host")
            return value

        if not address.is_global or address.is_multicast:
            raise ValueError("source_page_url must use a public host")
        return value

    @model_validator(mode="after")
    def validate_research_state(self) -> "BenchmarkSourceResearchRecord":
        if self.checked_on > date.today():
            raise ValueError("checked_on cannot be in the future")

        if self.finding in _FOUND_REFERENCE_KINDS:
            if self.source_page_url is None or self.source_title is None:
                raise ValueError(
                    "found structured references require source_page_url and source_title"
                )
        elif self.source_page_url is not None or self.source_title is not None:
            raise ValueError(
                "source_page_url and source_title must remain unset when no source is recorded"
            )

        return self
