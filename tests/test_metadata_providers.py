from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from rocksmith_cdlc_generator.metadata_providers import (
    MUSICBRAINZ_USER_AGENT,
    MetadataIdentificationReport,
    identify_musicbrainz,
    identify_project_metadata,
)
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    manifest = ProjectManifest(
        project_name="test-song",
        artist="Example Artist",
        title="Example Song",
        source_original_path="C:/Music/example.wav",
        source_project_path="source/example.wav",
        source_sha256="a" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=180.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )
    manifest.save(project)
    return project


def test_musicbrainz_query_is_scoped_and_identified() -> None:
    observed: dict[str, str] = {}

    def fetcher(url: str, user_agent: str) -> dict:
        observed["url"] = url
        observed["user_agent"] = user_agent
        return {"recordings": []}

    report = identify_musicbrainz(
        artist="Example Artist",
        title="Example Song",
        duration_seconds=180.0,
        fetcher=fetcher,
    )

    parsed = urlparse(observed["url"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "musicbrainz.org"
    assert params["fmt"] == ["json"]
    assert params["limit"] == ["5"]
    assert 'recording:"Example Song"' in params["query"][0]
    assert 'artist:"Example Artist"' in params["query"][0]
    assert observed["user_agent"] == MUSICBRAINZ_USER_AGENT
    assert "github.com/jweter/rocksmith-cdlc-generator" in observed["user_agent"]
    assert report.candidates == []


def test_duration_evidence_reranks_similar_provider_matches() -> None:
    def fetcher(url: str, user_agent: str) -> dict:
        del url, user_agent
        return {
            "recordings": [
                {
                    "id": "far",
                    "title": "Example Song",
                    "score": 100,
                    "length": 240000,
                    "artist-credit": [{"name": "Example Artist"}],
                },
                {
                    "id": "close",
                    "title": "Example Song",
                    "score": 98,
                    "length": 180500,
                    "artist-credit": [{"name": "Example Artist"}],
                    "first-release-date": "2001-02-03",
                    "releases": [{"title": "Example Album"}],
                },
            ]
        }

    report = identify_musicbrainz(
        artist="Example Artist",
        title="Example Song",
        duration_seconds=180.0,
        fetcher=fetcher,
    )

    assert [candidate.recording_id for candidate in report.candidates] == ["close", "far"]
    best = report.candidates[0]
    assert best.artist_credit == "Example Artist"
    assert best.duration_delta_seconds == 0.5
    assert best.first_release_date == "2001-02-03"
    assert best.release_titles == ["Example Album"]


def test_project_identification_is_cached_without_hidden_requery(tmp_path: Path) -> None:
    project = _project(tmp_path)
    calls = 0

    def fetcher(url: str, user_agent: str) -> dict:
        nonlocal calls
        del url, user_agent
        calls += 1
        return {
            "recordings": [
                {
                    "id": "recording-id",
                    "title": "Example Song",
                    "score": 100,
                    "length": 180000,
                    "artist-credit": [{"name": "Example Artist"}],
                }
            ]
        }

    first = identify_project_metadata(project, fetcher=fetcher)
    second = identify_project_metadata(project, fetcher=fetcher)

    assert first == second
    assert calls == 1
    report = MetadataIdentificationReport.model_validate_json(first.read_text(encoding="utf-8"))
    assert report.cache_key in first.name
    assert report.candidates[0].recording_id == "recording-id"


def test_refresh_explicitly_requeries_provider(tmp_path: Path) -> None:
    project = _project(tmp_path)
    calls = 0

    def fetcher(url: str, user_agent: str) -> dict:
        nonlocal calls
        del url, user_agent
        calls += 1
        return {"recordings": []}

    identify_project_metadata(project, fetcher=fetcher)
    identify_project_metadata(project, refresh=True, fetcher=fetcher)

    assert calls == 2


def test_cached_artifact_is_self_contained_json(tmp_path: Path) -> None:
    project = _project(tmp_path)

    def fetcher(url: str, user_agent: str) -> dict:
        del url, user_agent
        return {"recordings": []}

    output = identify_project_metadata(project, fetcher=fetcher)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["provider"] == "musicbrainz"
    assert payload["query_artist"] == "Example Artist"
    assert payload["query_title"] == "Example Song"
    assert payload["query_duration_seconds"] == 180.0
    assert payload["request_url"].startswith("https://musicbrainz.org/ws/2/recording/")
