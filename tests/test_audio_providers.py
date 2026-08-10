from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from rocksmith_cdlc_generator.audio_providers import (
    JAMENDO_USER_AGENT,
    ProviderAudioSearchReport,
    download_provider_candidate,
    search_jamendo,
    write_provider_search,
)


def _payload(*, allowed: bool = True) -> dict:
    return {
        "results": [
            {
                "id": "123",
                "name": "Test Song",
                "artist_name": "Test Artist",
                "album_name": "Test Album",
                "duration": 181,
                "releasedate": "2020-03-04",
                "license_ccurl": "https://creativecommons.org/licenses/by/4.0/",
                "audiodownload_allowed": allowed,
                "audiodownload": "https://cdn.example.test/test.flac" if allowed else "",
            }
        ]
    }


def test_jamendo_search_uses_download_permission_and_license_fields() -> None:
    observed: dict[str, str] = {}

    def fetcher(url: str, user_agent: str) -> dict:
        observed["url"] = url
        observed["user_agent"] = user_agent
        return _payload()

    report = search_jamendo("test rock", client_id="client-123", fetcher=fetcher)
    params = parse_qs(urlparse(observed["url"]).query)

    assert params["client_id"] == ["client-123"]
    assert params["search"] == ["test rock"]
    assert params["audiodlformat"] == ["flac"]
    assert observed["user_agent"] == JAMENDO_USER_AGENT
    candidate = report.candidates[0]
    assert candidate.download_allowed is True
    assert candidate.download_url == "https://cdn.example.test/test.flac"
    assert candidate.license_url == "https://creativecommons.org/licenses/by/4.0/"
    assert candidate.redistribution_rights_review_required is True


def test_client_id_can_come_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, str] = {}
    monkeypatch.setenv("JAMENDO_CLIENT_ID", "env-client")

    def fetcher(url: str, user_agent: str) -> dict:
        del user_agent
        observed["url"] = url
        return {"results": []}

    search_jamendo("bass", fetcher=fetcher)
    assert parse_qs(urlparse(observed["url"]).query)["client_id"] == ["env-client"]


def test_missing_client_id_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JAMENDO_CLIENT_ID", raising=False)
    with pytest.raises(ValueError, match="client id"):
        search_jamendo("bass")


def test_disallowed_track_cannot_be_downloaded(tmp_path: Path) -> None:
    report = ProviderAudioSearchReport(
        provider="jamendo",
        query="test",
        request_url="https://api.jamendo.com/v3.0/tracks/",
        candidates=search_jamendo(
            "test",
            client_id="client",
            fetcher=lambda url, ua: _payload(allowed=False),
        ).candidates,
    )
    report_path = write_provider_search(report, tmp_path / "search.json")

    with pytest.raises(PermissionError, match="does not allow"):
        download_provider_candidate(report_path, index=0, destination=tmp_path / "song.flac")


def test_download_writes_hash_and_provenance(tmp_path: Path) -> None:
    report = search_jamendo(
        "test",
        client_id="client",
        fetcher=lambda url, ua: _payload(),
    )
    report_path = write_provider_search(report, tmp_path / "search.json")
    audio_bytes = b"fake-flac-fixture"

    audio_path, receipt_path = download_provider_candidate(
        report_path,
        index=0,
        destination=tmp_path / "song.flac",
        downloader=lambda url, ua: audio_bytes,
    )

    assert audio_path.read_bytes() == audio_bytes
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["provider"] == "jamendo"
    assert receipt["provider_track_id"] == "123"
    assert receipt["provider_download_allowed"] is True
    assert receipt["redistribution_rights_review_required"] is True
    assert receipt["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert len(receipt["sha256"]) == 64


def test_non_https_download_url_is_rejected(tmp_path: Path) -> None:
    report = search_jamendo("test", client_id="client", fetcher=lambda url, ua: _payload())
    report.candidates[0].download_url = "http://example.test/song.flac"
    report_path = write_provider_search(report, tmp_path / "search.json")

    with pytest.raises(ValueError, match="HTTPS"):
        download_provider_candidate(report_path, index=0, destination=tmp_path / "song.flac")
