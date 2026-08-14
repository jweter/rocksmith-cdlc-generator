from __future__ import annotations

from enum import Enum
import ipaddress
from pathlib import Path
import re

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class SourceFamily(str, Enum):
    audio = "audio"
    notation = "notation"
    rocksmith_package = "rocksmith_package"
    unknown = "unknown"


class SourceFormat(str, Enum):
    wav = "wav"
    flac = "flac"
    mp3 = "mp3"
    m4a = "m4a"
    aac = "aac"
    ogg = "ogg"
    opus = "opus"
    midi = "midi"
    gp3 = "gp3"
    gp4 = "gp4"
    gp5 = "gp5"
    gpx = "gpx"
    gp = "gp"
    musicxml = "musicxml"
    mxl = "mxl"
    powertab = "powertab"
    tuxguitar = "tuxguitar"
    tabledit = "tabledit"
    abc = "abc"
    psarc = "psarc"
    unknown = "unknown"


class AdapterStatus(str, Enum):
    supported = "supported"
    optional_dependency = "optional_dependency"
    planned = "planned"
    reference_only = "reference_only"
    unknown = "unknown"


class SourceRightsClass(str, Enum):
    user_owned_local = "user_owned_local"
    licensed_download = "licensed_download"
    creative_commons = "creative_commons"
    public_domain = "public_domain"
    self_recorded = "self_recorded"
    streaming_reference_only = "streaming_reference_only"
    unknown = "unknown"


_EXTENSION_FORMATS: dict[str, SourceFormat] = {
    ".wav": SourceFormat.wav,
    ".flac": SourceFormat.flac,
    ".mp3": SourceFormat.mp3,
    ".m4a": SourceFormat.m4a,
    ".aac": SourceFormat.aac,
    ".ogg": SourceFormat.ogg,
    ".opus": SourceFormat.opus,
    ".mid": SourceFormat.midi,
    ".midi": SourceFormat.midi,
    ".gp3": SourceFormat.gp3,
    ".gp4": SourceFormat.gp4,
    ".gp5": SourceFormat.gp5,
    ".gpx": SourceFormat.gpx,
    ".gp": SourceFormat.gp,
    ".musicxml": SourceFormat.musicxml,
    ".xml": SourceFormat.musicxml,
    ".mxl": SourceFormat.mxl,
    ".ptb": SourceFormat.powertab,
    ".tg": SourceFormat.tuxguitar,
    ".tef": SourceFormat.tabledit,
    ".abc": SourceFormat.abc,
    ".psarc": SourceFormat.psarc,
}

_AUDIO_FORMATS = {
    SourceFormat.wav,
    SourceFormat.flac,
    SourceFormat.mp3,
    SourceFormat.m4a,
    SourceFormat.aac,
    SourceFormat.ogg,
    SourceFormat.opus,
}
_NOTATION_FORMATS = {
    SourceFormat.midi,
    SourceFormat.gp3,
    SourceFormat.gp4,
    SourceFormat.gp5,
    SourceFormat.gpx,
    SourceFormat.gp,
    SourceFormat.musicxml,
    SourceFormat.mxl,
    SourceFormat.powertab,
    SourceFormat.tuxguitar,
    SourceFormat.tabledit,
    SourceFormat.abc,
}

_ADAPTER_STATUS: dict[SourceFormat, AdapterStatus] = {
    SourceFormat.midi: AdapterStatus.supported,
    SourceFormat.gp3: AdapterStatus.optional_dependency,
    SourceFormat.gp4: AdapterStatus.optional_dependency,
    SourceFormat.gp5: AdapterStatus.optional_dependency,
    SourceFormat.musicxml: AdapterStatus.supported,
    SourceFormat.mxl: AdapterStatus.supported,
    SourceFormat.psarc: AdapterStatus.supported,
    SourceFormat.gpx: AdapterStatus.planned,
    SourceFormat.gp: AdapterStatus.planned,
    SourceFormat.powertab: AdapterStatus.planned,
    SourceFormat.tuxguitar: AdapterStatus.planned,
    SourceFormat.tabledit: AdapterStatus.planned,
    SourceFormat.abc: AdapterStatus.planned,
}
for _audio_format in _AUDIO_FORMATS:
    _ADAPTER_STATUS[_audio_format] = AdapterStatus.supported

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


def detect_source_format(filename: str | Path) -> SourceFormat:
    return _EXTENSION_FORMATS.get(Path(filename).suffix.lower(), SourceFormat.unknown)


def source_family(source_format: SourceFormat) -> SourceFamily:
    if source_format in _AUDIO_FORMATS:
        return SourceFamily.audio
    if source_format in _NOTATION_FORMATS:
        return SourceFamily.notation
    if source_format is SourceFormat.psarc:
        return SourceFamily.rocksmith_package
    return SourceFamily.unknown


def adapter_status(source_format: SourceFormat) -> AdapterStatus:
    return _ADAPTER_STATUS.get(source_format, AdapterStatus.unknown)


def _require_public_reference_url(value: HttpUrl) -> HttpUrl:
    if value.username is not None or value.password is not None:
        raise ValueError("reference_url must not contain embedded user information")
    host = value.host
    if host is None:
        raise ValueError("reference_url must use a public host")
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
            raise ValueError("reference_url must use a public host")
        return value
    if not address.is_global or address.is_multicast:
        raise ValueError("reference_url must use a public host")
    return value


class SourceIntakeDescriptor(BaseModel):
    """Pre-import classification for local material or reference-only sources.

    Format recognition is deliberately broader than parser support. A recognized
    format can be accepted into the workflow as a candidate even when its parser
    adapter is still planned. Rights classification is advisory metadata and does
    not silently promote a source to trusted benchmark ground truth.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(min_length=1)
    source_format: SourceFormat
    family: SourceFamily
    adapter_status: AdapterStatus
    rights_class: SourceRightsClass = SourceRightsClass.unknown
    local_bytes_available: bool = False
    reference_url: HttpUrl | None = None
    license_note: str | None = None

    @field_validator("display_name", "license_note")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("source intake text must contain a non-whitespace character")
        return stripped

    @field_validator("reference_url")
    @classmethod
    def validate_reference_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        return None if value is None else _require_public_reference_url(value)

    @model_validator(mode="after")
    def validate_use_boundary(self) -> "SourceIntakeDescriptor":
        if self.family != source_family(self.source_format):
            raise ValueError("source family does not match source format")

        reference_only = self.rights_class is SourceRightsClass.streaming_reference_only
        expected_status = AdapterStatus.reference_only if reference_only else adapter_status(self.source_format)
        if self.adapter_status != expected_status:
            raise ValueError("adapter status does not match source intake mode")

        if reference_only:
            if self.local_bytes_available:
                raise ValueError("streaming-reference sources cannot be marked as local ingest bytes")
            if self.reference_url is None:
                raise ValueError("streaming-reference sources require reference_url")
        elif self.reference_url is not None and self.local_bytes_available:
            # A local file may retain an origin URL for provenance; that is allowed.
            pass
        return self

    @property
    def requires_human_rights_review(self) -> bool:
        return self.rights_class is SourceRightsClass.unknown

    @property
    def can_ingest_local_bytes(self) -> bool:
        return self.local_bytes_available and self.rights_class is not SourceRightsClass.streaming_reference_only


def describe_local_source(
    path: str | Path,
    *,
    rights_class: SourceRightsClass = SourceRightsClass.unknown,
    license_note: str | None = None,
) -> SourceIntakeDescriptor:
    source_format = detect_source_format(path)
    return SourceIntakeDescriptor(
        display_name=Path(path).name,
        source_format=source_format,
        family=source_family(source_format),
        adapter_status=adapter_status(source_format),
        rights_class=rights_class,
        local_bytes_available=True,
        license_note=license_note,
    )


def describe_streaming_reference(url: str, *, display_name: str) -> SourceIntakeDescriptor:
    return SourceIntakeDescriptor(
        display_name=display_name,
        source_format=SourceFormat.unknown,
        family=SourceFamily.unknown,
        adapter_status=AdapterStatus.reference_only,
        rights_class=SourceRightsClass.streaming_reference_only,
        local_bytes_available=False,
        reference_url=url,
    )
