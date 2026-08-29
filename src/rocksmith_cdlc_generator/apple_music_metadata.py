from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .benchmark_metadata import BenchmarkCatalogMetadata, BenchmarkMetadataQuery

ITUNES_SEARCH_API_ROOT = "https://itunes.apple.com/search"
APPLE_MUSIC_PROVIDER_NAME = "apple_music"


def _default_fetch(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS Apple endpoint
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Apple Music search failed with HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Apple Music search failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Apple Music search returned invalid JSON") from exc


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _parse_release_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _to_catalog_metadata(track: dict[str, Any]) -> BenchmarkCatalogMetadata | None:
    track_id = track.get("trackId")
    artist_name = track.get("artistName")
    track_name = track.get("trackName")
    source_url = track.get("trackViewUrl") or track.get("collectionViewUrl")
    if track_id is None or not artist_name or not track_name or not source_url:
        return None

    duration_ms = track.get("trackTimeMillis")
    duration_seconds = (
        duration_ms / 1000.0 if isinstance(duration_ms, (int, float)) and duration_ms > 0 else None
    )
    collection_name = track.get("collectionName")

    return BenchmarkCatalogMetadata(
        provider=APPLE_MUSIC_PROVIDER_NAME,
        provider_track_id=str(track_id),
        artist=str(artist_name),
        title=str(track_name),
        album=str(collection_name) if collection_name else None,
        duration_seconds=duration_seconds,
        release_date=_parse_release_date(track.get("releaseDate")),
        source_page_url=str(source_url),
    )


class AppleMusicMetadataProvider:
    """Looks up redistributable catalog metadata from Apple's public iTunes Search API.

    Uses only the unauthenticated ``itunes.apple.com/search`` endpoint -- no Apple
    Developer account, MusicKit token, or other paid/credentialed access. ISRC is not
    exposed by this endpoint and is intentionally left unset rather than guessed; a
    future provider backed by an authenticated catalog could add it separately.
    """

    name = APPLE_MUSIC_PROVIDER_NAME

    def __init__(
        self,
        *,
        country: str = "US",
        limit: int = 10,
        fetcher: Callable[[str], dict[str, Any]] = _default_fetch,
    ) -> None:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        self._country = country
        self._limit = limit
        self._fetcher = fetcher

    def lookup(self, query: BenchmarkMetadataQuery) -> BenchmarkCatalogMetadata | None:
        term = f"{query.artist} {query.title}"
        request_url = (
            ITUNES_SEARCH_API_ROOT
            + "?"
            + urlencode(
                {
                    "term": term,
                    "media": "music",
                    "entity": "musicTrack",
                    "country": self._country,
                    "limit": self._limit,
                }
            )
        )
        payload = self._fetcher(request_url)
        results = payload.get("results")
        if not isinstance(results, list):
            return None

        expected_artist = _normalize(query.artist)
        expected_title = _normalize(query.title)
        for track in results:
            if not isinstance(track, dict):
                continue
            artist_name = track.get("artistName")
            track_name = track.get("trackName")
            if not isinstance(artist_name, str) or not isinstance(track_name, str):
                continue
            if _normalize(artist_name) != expected_artist or _normalize(track_name) != expected_title:
                continue
            metadata = _to_catalog_metadata(track)
            if metadata is not None:
                return metadata
        return None
