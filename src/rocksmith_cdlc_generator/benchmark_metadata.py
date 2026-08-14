from __future__ import annotations

from datetime import date, datetime, timezone
import ipaddress
import re
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


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


class BenchmarkMetadataQuery(BaseModel):
    """Identity used to ask an external provider for redistributable catalog metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_id: str = Field(pattern=r"^BMARK-[0-9]{3}$")
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)

    @field_validator("artist", "title")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("metadata query text must not be blank")
        return value


class BenchmarkCatalogMetadata(BaseModel):
    """Redistributable catalog metadata returned by a provider.

    This model intentionally excludes audio URLs, local paths, credentials, and source
    media. Provider output is descriptive metadata only and is never benchmark ground
    truth by itself.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1)
    provider_track_id: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    album: str | None = None
    duration_seconds: float | None = Field(default=None, gt=0)
    release_date: date | None = None
    isrc: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$")
    source_page_url: HttpUrl

    @field_validator("provider", "provider_track_id", "artist", "title", "album", "isrc")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("catalog metadata text must not be blank")
        return value

    @field_validator("source_page_url")
    @classmethod
    def require_public_source_url(cls, value: HttpUrl) -> HttpUrl:
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


class BenchmarkMetadataReceipt(BaseModel):
    """Auditable result of one metadata lookup without persisting provider secrets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    benchmark_id: str = Field(pattern=r"^BMARK-[0-9]{3}$")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: BenchmarkCatalogMetadata
    human_review_required: bool = True


@runtime_checkable
class BenchmarkMetadataProvider(Protocol):
    """Pluggable provider interface; network-specific implementations remain optional."""

    name: str

    def lookup(self, query: BenchmarkMetadataQuery) -> BenchmarkCatalogMetadata | None:
        """Return the best catalog match, or None when no confident match is available."""


def enrich_benchmark_metadata(
    query: BenchmarkMetadataQuery,
    provider: BenchmarkMetadataProvider,
) -> BenchmarkMetadataReceipt | None:
    """Lookup metadata and wrap it in an auditable, human-review-gated receipt."""

    metadata = provider.lookup(query)
    if metadata is None:
        return None
    if metadata.provider.strip().casefold() != provider.name.strip().casefold():
        raise ValueError("provider result name does not match the provider contract")
    return BenchmarkMetadataReceipt(
        benchmark_id=query.benchmark_id,
        metadata=metadata,
        human_review_required=True,
    )
