from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.source_intake import SourceRightsClass
from rocksmith_cdlc_generator.source_router import route_local_source


@pytest.mark.parametrize("filename", ["song.wav", "song.flac", "song.mp3", "song.m4a", "song.aac", "song.ogg", "song.opus"])
def test_audio_routes_to_project_ingest(filename: str) -> None:
    route = route_local_source(filename, rights_class=SourceRightsClass.user_owned_local)

    assert route.action == "project_audio"
    assert route.importer_command == "new"
    assert route.immediately_processable is True


@pytest.mark.parametrize(
    ("filename", "action", "command"),
    [
        ("bass.mid", "import_midi", "import-midi"),
        ("bass.midi", "import_midi", "import-midi"),
        ("bass.gp3", "import_guitarpro", "import-gp"),
        ("bass.gp4", "import_guitarpro", "import-gp"),
        ("bass.gp5", "import_guitarpro", "import-gp"),
        ("bass.musicxml", "import_musicxml", "import-musicxml"),
        ("bass.xml", "import_musicxml", "import-musicxml"),
        ("bass.mxl", "import_musicxml", "import-musicxml"),
        ("custom.psarc", "import_psarc", "import-psarc"),
    ],
)
def test_existing_symbolic_adapters_have_deterministic_routes(
    filename: str, action: str, command: str
) -> None:
    route = route_local_source(filename)

    assert route.action == action
    assert route.importer_command == command
    assert route.immediately_processable is True


@pytest.mark.parametrize("filename", ["score.gpx", "score.gp", "score.ptb", "score.tg", "score.tef", "score.abc"])
def test_recognized_future_formats_are_queued_not_rejected(filename: str) -> None:
    route = route_local_source(filename)

    assert route.action == "queue_adapter"
    assert route.importer_command is None
    assert route.immediately_processable is False


def test_unknown_extension_is_rejected_without_guessing_parser() -> None:
    route = route_local_source("mystery.bin")

    assert route.action == "reject_unknown"
    assert route.importer_command is None
    assert route.immediately_processable is False


def test_routing_preserves_rights_review_boundary() -> None:
    unknown = route_local_source("song.flac")
    owned = route_local_source("song.flac", rights_class=SourceRightsClass.user_owned_local)

    assert unknown.descriptor.requires_human_rights_review is True
    assert owned.descriptor.requires_human_rights_review is False
    assert unknown.action == owned.action == "project_audio"
