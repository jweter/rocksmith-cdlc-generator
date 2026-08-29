from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from rocksmith_cdlc_generator.apple_music_metadata import (
    APPLE_MUSIC_PROVIDER_NAME,
    AppleMusicMetadataProvider,
)
from rocksmith_cdlc_generator.benchmark_metadata import (
    BenchmarkMetadataQuery,
    enrich_benchmark_metadata,
)

_QUERY = BenchmarkMetadataQuery(
    benchmark_id="BMARK-001",
    artist="Lamb of God",
    title="Laid to Rest",
)


def _track(**overrides: Any) -> dict[str, Any]:
    track = {
        "trackId": 12345,
        "artistName": "Lamb of God",
        "trackName": "Laid to Rest",
        "collectionName": "Ashes of the Wake",
        "trackTimeMillis": 231000,
        "releaseDate": "2004-08-31T07:00:00Z",
        "trackViewUrl": "https://music.apple.com/us/album/laid-to-rest/12345",
    }
    track.update(overrides)
    return track


def test_lookup_request_is_scoped_to_public_search_endpoint() -> None:
    observed: dict[str, str] = {}

    def fetcher(url: str) -> dict:
        observed["url"] = url
        return {"results": []}

    AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY)

    parsed = urlparse(observed["url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "itunes.apple.com"
    assert parsed.path == "/search"
    assert params["term"] == ["Lamb of God Laid to Rest"]
    assert params["entity"] == ["musicTrack"]
    assert params["media"] == ["music"]


def test_lookup_maps_matching_track_to_catalog_metadata() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {"results": [_track()]}

    metadata = AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY)

    assert metadata is not None
    assert metadata.provider == APPLE_MUSIC_PROVIDER_NAME
    assert metadata.provider_track_id == "12345"
    assert metadata.artist == "Lamb of God"
    assert metadata.title == "Laid to Rest"
    assert metadata.album == "Ashes of the Wake"
    assert metadata.duration_seconds == 231.0
    assert metadata.release_date == date(2004, 8, 31)
    assert metadata.isrc is None
    assert str(metadata.source_page_url).startswith("https://music.apple.com/")


def test_lookup_skips_results_that_do_not_match_artist_or_title() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {
            "results": [
                _track(artistName="Lamb of God", trackName="11th Hour"),
                _track(artistName="Trivium", trackName="Laid to Rest"),
                _track(trackId=99999),
            ]
        }

    metadata = AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY)

    assert metadata is not None
    assert metadata.provider_track_id == "99999"


def test_lookup_is_case_and_whitespace_insensitive() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {"results": [_track(artistName="  LAMB OF   GOD ", trackName="laid to rest")]}

    assert AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY) is not None


def test_lookup_returns_none_when_no_confident_match() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {"results": [_track(artistName="Some Cover Band")]}

    assert AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY) is None


def test_lookup_returns_none_on_missing_or_malformed_results() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {}

    assert AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY) is None


def test_lookup_skips_track_missing_required_fields_and_keeps_searching() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {"results": [_track(trackViewUrl=None, collectionViewUrl=None), _track(trackId=54321)]}

    metadata = AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY)

    assert metadata is not None
    assert metadata.provider_track_id == "54321"


def test_lookup_omits_duration_when_missing_or_non_positive() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {"results": [_track(trackTimeMillis=0)]}

    metadata = AppleMusicMetadataProvider(fetcher=fetcher).lookup(_QUERY)

    assert metadata is not None
    assert metadata.duration_seconds is None


def test_invalid_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="limit"):
        AppleMusicMetadataProvider(limit=0)


def test_provider_integrates_with_enrich_benchmark_metadata() -> None:
    def fetcher(url: str) -> dict:
        del url
        return {"results": [_track()]}

    receipt = enrich_benchmark_metadata(_QUERY, AppleMusicMetadataProvider(fetcher=fetcher))

    assert receipt is not None
    assert receipt.metadata.provider == APPLE_MUSIC_PROVIDER_NAME
    assert receipt.human_review_required is True
