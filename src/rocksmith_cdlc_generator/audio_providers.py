from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

JAMENDO_TRACKS_API = "https://api.jamendo.com/v3.0/tracks/"
JAMENDO_USER_AGENT = "RocksmithCDLCGenerator/0.1.0 (https://github.com/jweter/rocksmith-cdlc-generator)"


class ProviderAudioCandidate(BaseModel):
    provider: str
    provider_track_id: str
    title: str
    artist: str
    album: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0.0)
    release_date: str | None = None
    license_url: str | None = None
    download_allowed: bool = False
    download_url: str | None = None
    redistribution_rights_review_required: bool = True


class ProviderAudioSearchReport(BaseModel):
    schema_version: int = 1
    provider: str
    query: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_url: str
    candidates: list[ProviderAudioCandidate]


class ProviderAudioReceipt(BaseModel):
    schema_version: int = 1
    provider: str
    provider_track_id: str
    source_report: str
    selected_index: int = Field(ge=0)
    downloaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    local_path: str
    sha256: str
    size_bytes: int = Field(gt=0)
    license_url: str | None = None
    provider_download_allowed: bool
    redistribution_rights_review_required: bool = True


def _default_json_fetch(url: str, user_agent: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": user_agent})
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS provider endpoint
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Provider request failed with HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Provider request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Provider returned invalid JSON") from exc


def _default_download(url: str, user_agent: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Provider download URL must use HTTPS")
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310 - URL came from validated provider report
            data = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Provider download failed with HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Provider download failed: {exc.reason}") from exc
    if not data:
        raise RuntimeError("Provider returned an empty audio file")
    return data


def _normalize_jamendo_track(item: dict[str, Any]) -> ProviderAudioCandidate | None:
    track_id = str(item.get("id", "")).strip()
    title = str(item.get("name", "")).strip()
    artist = str(item.get("artist_name", "")).strip()
    if not track_id or not title or not artist:
        return None

    raw_duration = item.get("duration")
    try:
        duration = float(raw_duration) if raw_duration is not None else None
    except (TypeError, ValueError):
        duration = None

    allowed = bool(item.get("audiodownload_allowed", False))
    download_url = str(item.get("audiodownload") or "").strip() or None
    if not allowed:
        download_url = None

    return ProviderAudioCandidate(
        provider="jamendo",
        provider_track_id=track_id,
        title=title,
        artist=artist,
        album=(str(item.get("album_name") or "").strip() or None),
        duration_seconds=duration,
        release_date=(str(item.get("releasedate") or "").strip() or None),
        license_url=(str(item.get("license_ccurl") or "").strip() or None),
        download_allowed=allowed,
        download_url=download_url,
        redistribution_rights_review_required=True,
    )


def search_jamendo(
    query: str,
    *,
    client_id: str | None = None,
    limit: int = 10,
    fetcher: Callable[[str, str], dict[str, Any]] = _default_json_fetch,
) -> ProviderAudioSearchReport:
    query = query.strip()
    if not query:
        raise ValueError("Provider search query must not be empty")
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    client_id = (client_id or os.getenv("JAMENDO_CLIENT_ID") or "").strip()
    if not client_id:
        raise ValueError("Jamendo requires a client id; pass --client-id or set JAMENDO_CLIENT_ID")

    request_url = JAMENDO_TRACKS_API + "?" + urlencode(
        {
            "client_id": client_id,
            "format": "json",
            "limit": limit,
            "search": query,
            "include": "licenses",
            "audiodlformat": "flac",
        }
    )
    payload = fetcher(request_url, JAMENDO_USER_AGENT)
    results = payload.get("results") or []
    if not isinstance(results, list):
        raise RuntimeError("Jamendo response did not contain a valid results list")

    candidates = []
    for item in results:
        if isinstance(item, dict):
            candidate = _normalize_jamendo_track(item)
            if candidate is not None:
                candidates.append(candidate)

    return ProviderAudioSearchReport(
        provider="jamendo",
        query=query,
        request_url=request_url,
        candidates=candidates,
    )


def write_provider_search(report: ProviderAudioSearchReport, output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return output


def download_provider_candidate(
    report_path: Path,
    *,
    index: int,
    destination: Path,
    downloader: Callable[[str, str], bytes] = _default_download,
) -> tuple[Path, Path]:
    report_path = report_path.resolve()
    report = ProviderAudioSearchReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    if index < 0 or index >= len(report.candidates):
        raise IndexError(f"Candidate index {index} is out of range for {len(report.candidates)} candidates")

    candidate = report.candidates[index]
    if not candidate.download_allowed or not candidate.download_url:
        raise PermissionError("Provider does not allow this track to be downloaded through the application")
    parsed = urlparse(candidate.download_url)
    if parsed.scheme != "https":
        raise ValueError("Provider download URL must use HTTPS")

    data = downloader(candidate.download_url, JAMENDO_USER_AGENT)
    if not data:
        raise RuntimeError("Provider returned an empty audio file")

    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()

    receipt = ProviderAudioReceipt(
        provider=candidate.provider,
        provider_track_id=candidate.provider_track_id,
        source_report=str(report_path),
        selected_index=index,
        local_path=str(destination),
        sha256=digest,
        size_bytes=len(data),
        license_url=candidate.license_url,
        provider_download_allowed=candidate.download_allowed,
        redistribution_rights_review_required=True,
    )
    receipt_path = destination.with_suffix(destination.suffix + ".provenance.json")
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return destination, receipt_path
