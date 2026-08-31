from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from .models import ProjectManifest

MUSICBRAINZ_API_ROOT = "https://musicbrainz.org/ws/2/recording/"
MUSICBRAINZ_USER_AGENT = "RocksmithCDLCGenerator/0.1.0 (https://github.com/jweter/rocksmith-cdlc-generator)"


class MetadataCandidate(BaseModel):
    provider: str = "musicbrainz"
    recording_id: str
    title: str
    artist_credit: str
    provider_score: float = Field(ge=0.0, le=1.0)
    duration_ms: int | None = Field(default=None, ge=0)
    duration_delta_seconds: float | None = Field(default=None, ge=0.0)
    first_release_date: str | None = None
    release_titles: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class MetadataIdentificationReport(BaseModel):
    schema_version: int = 1
    provider: str = "musicbrainz"
    query_artist: str | None = None
    query_title: str
    query_duration_seconds: float | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_url: str
    cache_key: str
    candidates: list[MetadataCandidate]


class SelectedMetadata(BaseModel):
    schema_version: int = 1
    provider: str
    source_report: str
    selected_index: int = Field(ge=0)
    selected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    candidate: MetadataCandidate


def _escape_lucene(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _build_query(*, artist: str | None, title: str) -> str:
    terms = [f"recording:{_escape_lucene(title)}"]
    if artist:
        terms.append(f"artist:{_escape_lucene(artist)}")
    return " AND ".join(terms)


def _artist_credit(recording: dict[str, Any]) -> str:
    credits = recording.get("artist-credit") or []
    parts: list[str] = []
    for credit in credits:
        if isinstance(credit, str):
            parts.append(credit)
            continue
        if not isinstance(credit, dict):
            continue
        name = credit.get("name") or (credit.get("artist") or {}).get("name")
        if name:
            parts.append(str(name))
        joinphrase = credit.get("joinphrase")
        if joinphrase:
            parts.append(str(joinphrase))
    return "".join(parts).strip()


def _duration_confidence(candidate_ms: int | None, source_seconds: float | None) -> tuple[float, float | None]:
    if candidate_ms is None or source_seconds is None or source_seconds <= 0:
        return 0.5, None
    delta = abs(candidate_ms / 1000.0 - source_seconds)
    # Full credit within one second; then decay smoothly. Ten seconds is already weak evidence.
    confidence = math.exp(-max(0.0, delta - 1.0) / 6.0)
    return max(0.0, min(1.0, confidence)), delta


def _normalize_candidate(recording: dict[str, Any], source_seconds: float | None) -> MetadataCandidate:
    raw_score = recording.get("score", 0)
    try:
        provider_score = max(0.0, min(1.0, float(raw_score) / 100.0))
    except (TypeError, ValueError):
        provider_score = 0.0

    length = recording.get("length")
    try:
        duration_ms = int(length) if length is not None else None
    except (TypeError, ValueError):
        duration_ms = None

    duration_score, duration_delta = _duration_confidence(duration_ms, source_seconds)
    confidence = provider_score if source_seconds is None else provider_score * 0.75 + duration_score * 0.25

    releases = recording.get("releases") or []
    release_titles = sorted(
        {
            str(release.get("title"))
            for release in releases
            if isinstance(release, dict) and release.get("title")
        }
    )

    return MetadataCandidate(
        recording_id=str(recording.get("id", "")),
        title=str(recording.get("title", "")),
        artist_credit=_artist_credit(recording),
        provider_score=provider_score,
        duration_ms=duration_ms,
        duration_delta_seconds=duration_delta,
        first_release_date=recording.get("first-release-date"),
        release_titles=release_titles,
        confidence=max(0.0, min(1.0, confidence)),
    )


def _default_fetch(url: str, user_agent: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS MusicBrainz endpoint
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"MusicBrainz request failed with HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"MusicBrainz request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("MusicBrainz returned invalid JSON") from exc


def identify_musicbrainz(
    *,
    artist: str | None,
    title: str,
    duration_seconds: float | None,
    limit: int = 5,
    fetcher: Callable[[str, str], dict[str, Any]] = _default_fetch,
) -> MetadataIdentificationReport:
    if not title.strip():
        raise ValueError("A non-empty title is required for metadata identification")
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")

    query = _build_query(artist=artist, title=title)
    request_url = MUSICBRAINZ_API_ROOT + "?" + urlencode({"query": query, "fmt": "json", "limit": limit})
    payload = fetcher(request_url, MUSICBRAINZ_USER_AGENT)
    recordings = payload.get("recordings")
    if recordings is None:
        recordings = []
    if not isinstance(recordings, list):
        raise RuntimeError("MusicBrainz response did not contain a valid recordings list")

    candidates = [_normalize_candidate(item, duration_seconds) for item in recordings if isinstance(item, dict)]
    candidates = [candidate for candidate in candidates if candidate.recording_id and candidate.title]
    candidates.sort(
        key=lambda candidate: (
            candidate.confidence,
            candidate.provider_score,
            -(candidate.duration_delta_seconds or 0.0),
        ),
        reverse=True,
    )

    cache_material = json.dumps(
        {
            "provider": "musicbrainz",
            "artist": artist,
            "title": title,
            "duration_seconds": duration_seconds,
            "limit": limit,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    cache_key = hashlib.sha256(cache_material).hexdigest()[:16]

    return MetadataIdentificationReport(
        query_artist=artist,
        query_title=title,
        query_duration_seconds=duration_seconds,
        request_url=request_url,
        cache_key=cache_key,
        candidates=candidates,
    )


def identify_project_metadata(
    project_dir: Path,
    *,
    limit: int = 5,
    refresh: bool = False,
    fetcher: Callable[[str, str], dict[str, Any]] = _default_fetch,
) -> Path:
    project_dir = project_dir.resolve()
    manifest = ProjectManifest.load(project_dir)
    metadata_dir = project_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    cache_material = json.dumps(
        {
            "provider": "musicbrainz",
            "artist": manifest.artist,
            "title": manifest.title,
            "duration_seconds": manifest.source_metadata.duration_seconds,
            "limit": limit,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    cache_key = hashlib.sha256(cache_material).hexdigest()[:16]
    output = metadata_dir / f"musicbrainz-{cache_key}.json"

    if output.exists() and not refresh:
        # Validate the cached artifact before trusting it.
        MetadataIdentificationReport.model_validate_json(output.read_text(encoding="utf-8"))
        return output

    report = identify_musicbrainz(
        artist=manifest.artist,
        title=manifest.title,
        duration_seconds=manifest.source_metadata.duration_seconds,
        limit=limit,
        fetcher=fetcher,
    )
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return output


def select_project_metadata(project_dir: Path, report_path: Path, *, index: int) -> Path:
    project_dir = project_dir.resolve()
    report_path = report_path.resolve()
    metadata_dir = (project_dir / "metadata").resolve()
    try:
        report_path.relative_to(metadata_dir)
    except ValueError as exc:
        raise ValueError("Metadata report must be located beneath the project's metadata directory") from exc

    report = MetadataIdentificationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    if index < 0 or index >= len(report.candidates):
        raise IndexError(f"Candidate index {index} is out of range for {len(report.candidates)} candidates")

    selected = SelectedMetadata(
        provider=report.provider,
        source_report=report_path.relative_to(project_dir).as_posix(),
        selected_index=index,
        candidate=report.candidates[index],
    )
    output = metadata_dir / "selected.json"
    output.write_text(selected.model_dump_json(indent=2), encoding="utf-8")
    return output
