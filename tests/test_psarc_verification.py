from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.psarc_verification import validate_structure_payload


def _valid_payload() -> dict:
    return {
        "entryCount": 12,
        "bassSng": ["songs/bin/generic/example_bass.sng"],
        "manifests": ["manifests/songs_dlc_example.json"],
        "audioWem": ["audio/windows/example.wem"],
        "soundBanks": ["audio/windows/song_example.bnk"],
        "xblocks": ["gamexblocks/nsongs/example.xblock"],
        "albumArt": ["gfxassets/album_art/album_example_256.dds"],
    }


def test_valid_single_song_bass_structure_passes() -> None:
    validate_structure_payload(_valid_payload())


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("bassSng", "Bass SNG"),
        ("manifests", "manifest JSON"),
        ("audioWem", "audio WEM"),
        ("soundBanks", "sound bank"),
        ("xblocks", "xblock"),
        ("albumArt", "album art"),
    ],
)
def test_missing_required_package_category_is_rejected(field: str, label: str) -> None:
    payload = _valid_payload()
    payload[field] = []
    with pytest.raises(ValueError, match=label):
        validate_structure_payload(payload)


def test_song_pack_with_multiple_xblocks_is_rejected() -> None:
    payload = _valid_payload()
    payload["xblocks"] = ["one.xblock", "two.xblock"]
    with pytest.raises(ValueError, match="exactly one xblock"):
        validate_structure_payload(payload)
