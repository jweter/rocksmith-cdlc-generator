from __future__ import annotations

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.source_intake import (
    AdapterStatus,
    SourceFamily,
    SourceFormat,
    SourceIntakeDescriptor,
    SourceRightsClass,
    adapter_status,
    describe_local_source,
    describe_streaming_reference,
    detect_source_format,
    source_family,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("song.wav", SourceFormat.wav),
        ("song.flac", SourceFormat.flac),
        ("song.mp3", SourceFormat.mp3),
        ("song.m4a", SourceFormat.m4a),
        ("song.aac", SourceFormat.aac),
        ("song.ogg", SourceFormat.ogg),
        ("song.opus", SourceFormat.opus),
        ("chart.mid", SourceFormat.midi),
        ("chart.midi", SourceFormat.midi),
        ("chart.gp3", SourceFormat.gp3),
        ("chart.gp4", SourceFormat.gp4),
        ("chart.gp5", SourceFormat.gp5),
        ("chart.gpx", SourceFormat.gpx),
        ("chart.gp", SourceFormat.gp),
        ("chart.musicxml", SourceFormat.musicxml),
        ("chart.xml", SourceFormat.musicxml),
        ("chart.mxl", SourceFormat.mxl),
        ("chart.ptb", SourceFormat.powertab),
        ("chart.tg", SourceFormat.tuxguitar),
        ("chart.tef", SourceFormat.tabledit),
        ("chart.abc", SourceFormat.abc),
        ("selected.psarc", SourceFormat.psarc),
    ],
)
def test_detects_broad_source_formats(filename: str, expected: SourceFormat) -> None:
    assert detect_source_format(filename) is expected


def test_recognition_is_broader_than_current_parser_support() -> None:
    assert source_family(SourceFormat.gpx) is SourceFamily.notation
    assert adapter_status(SourceFormat.gpx) is AdapterStatus.planned
    assert adapter_status(SourceFormat.gp5) is AdapterStatus.optional_dependency
    assert adapter_status(SourceFormat.midi) is AdapterStatus.supported
    assert adapter_status(SourceFormat.musicxml) is AdapterStatus.supported


def test_unknown_local_format_remains_accepted_for_review() -> None:
    descriptor = describe_local_source("candidate.weird")

    assert descriptor.source_format is SourceFormat.unknown
    assert descriptor.family is SourceFamily.unknown
    assert descriptor.adapter_status is AdapterStatus.unknown
    assert descriptor.local_bytes_available is True
    assert descriptor.can_ingest_local_bytes is True
    assert descriptor.requires_human_rights_review is True


def test_local_rights_classes_do_not_imply_redistribution_or_ground_truth() -> None:
    descriptor = describe_local_source(
        "owned.flac",
        rights_class=SourceRightsClass.user_owned_local,
    )

    assert descriptor.family is SourceFamily.audio
    assert descriptor.can_ingest_local_bytes is True
    assert descriptor.requires_human_rights_review is False


def test_streaming_reference_is_discovery_only() -> None:
    descriptor = describe_streaming_reference(
        "https://www.youtube.com/watch?v=example",
        display_name="Official song reference",
    )

    assert descriptor.rights_class is SourceRightsClass.streaming_reference_only
    assert descriptor.adapter_status is AdapterStatus.reference_only
    assert descriptor.can_ingest_local_bytes is False
    assert descriptor.reference_url is not None


def test_streaming_reference_cannot_be_marked_as_ingest_bytes() -> None:
    with pytest.raises(ValidationError, match="cannot be marked as local ingest bytes"):
        SourceIntakeDescriptor(
            display_name="stream",
            source_format=SourceFormat.unknown,
            family=SourceFamily.unknown,
            adapter_status=AdapterStatus.reference_only,
            rights_class=SourceRightsClass.streaming_reference_only,
            local_bytes_available=True,
            reference_url="https://example.com/watch/1",
        )


def test_reference_urls_reject_credentials_and_non_public_hosts() -> None:
    for url in (
        "https://user:secret@example.com/watch/1",
        "http://localhost/watch/1",
        "http://127.0.0.1/watch/1",
        "http://10.0.0.8/watch/1",
        "https://media.example/watch/1",
        "https://host.home.arpa/watch/1",
    ):
        with pytest.raises(ValidationError, match="reference_url"):
            describe_streaming_reference(url, display_name="reference")


def test_display_and_license_text_are_trimmed() -> None:
    descriptor = describe_local_source(
        "song.wav",
        rights_class=SourceRightsClass.creative_commons,
        license_note="  CC BY 4.0  ",
    )

    assert descriptor.display_name == "song.wav"
    assert descriptor.license_note == "CC BY 4.0"
