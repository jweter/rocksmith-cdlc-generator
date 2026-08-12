from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ARTIST_KEYS = ("colArtist", "Artist", "artist", "ArtistName", "artist_name")
_TITLE_KEYS = ("colTitle", "SongTitle", "Title", "title", "Song", "song", "SongName", "song_name")
_ARRANGEMENT_KEYS = ("colArrangements", "Arrangements", "arrangements", "Arrangement", "arrangement")
_TUNING_KEYS = ("colTunings", "Tuning", "tuning", "Tunings", "tunings")
_REPAIR_STATUS_KEYS = ("colRepairStatus", "RepairStatus", "repair_status")
_TAGGED_KEYS = ("colTagged", "Tagged", "tagged")
_ROW_CONTAINER_KEYS = (
    "dgvSongsMaster",
    "SongsMasterGrid",
    "songs",
    "Songs",
    "rows",
    "Rows",
    "data",
    "Data",
)


class CandidateCheckError(ValueError):
    """Raised when a local catalog cannot be interpreted safely."""


@dataclass(frozen=True)
class CatalogSong:
    artist: str
    title: str
    arrangements: tuple[str, ...] = ()
    tunings: tuple[str, ...] = ()
    library_kind: str = "unknown"


@dataclass(frozen=True)
class CandidateCheckResult:
    artist: str
    title: str
    match_type: str
    catalog_path: Path
    catalog_sha256: str
    catalog_modified_utc: str
    matches: tuple[CatalogSong, ...]
    same_artist: tuple[CatalogSong, ...]

    def to_dict(self) -> dict[str, Any]:
        def song(item: CatalogSong) -> dict[str, Any]:
            return {
                "artist": item.artist,
                "title": item.title,
                "arrangements": list(item.arrangements),
                "tunings": list(item.tunings),
                "library_kind": item.library_kind,
            }

        return {
            "artist": self.artist,
            "title": self.title,
            "match_type": self.match_type,
            "catalog": {
                "path": str(self.catalog_path),
                "sha256": self.catalog_sha256,
                "modified_utc": self.catalog_modified_utc,
            },
            "matches": [song(item) for item in self.matches],
            "same_artist": [song(item) for item in self.same_artist],
        }


@dataclass(frozen=True)
class LibrarySummary:
    catalog_path: Path
    catalog_sha256: str
    catalog_modified_utc: str
    row_count: int
    unique_artist_count: int
    unique_song_count: int
    library_kind_counts: dict[str, int]
    arrangement_counts: dict[str, int]
    tuning_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog": {
                "path": str(self.catalog_path),
                "sha256": self.catalog_sha256,
                "modified_utc": self.catalog_modified_utc,
            },
            "row_count": self.row_count,
            "unique_artist_count": self.unique_artist_count,
            "unique_song_count": self.unique_song_count,
            "library_kind_counts": dict(self.library_kind_counts),
            "arrangement_counts": dict(self.arrangement_counts),
            "tuning_counts": dict(self.tuning_counts),
        }


def normalize_name(value: str) -> str:
    """Normalize names while preserving punctuation-only identities deterministically."""

    stripped = value.strip()
    decomposed = unicodedata.normalize("NFKD", stripped)
    asciiish = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    normalized = "".join(ch.casefold() for ch in asciiish if ch.isalnum())
    return normalized or stripped.casefold()


def _identity_key(value: str) -> str:
    return normalize_name(value)


def _first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _split_metadata(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return tuple(part.strip() for part in re.split(r"[;,|]", value) if part.strip())
    return ()


def _first_metadata(row: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, ...]:
    for key in keys:
        if key in row:
            values = _split_metadata(row[key])
            if values:
                return values
    return ()


def _library_kind(row: dict[str, Any]) -> str:
    repair_status = (_first_text(row, _REPAIR_STATUS_KEYS) or "").casefold()
    tagged = (_first_text(row, _TAGGED_KEYS) or "").casefold()
    if repair_status == "odlc" or tagged == "odlc":
        return "official_dlc"
    if repair_status or tagged:
        return "custom_or_local"
    return "unknown"


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in _ROW_CONTAINER_KEYS:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                rows = candidate
                break
        if rows is None:
            raise CandidateCheckError(
                "CFSM JSON must be a row list or contain one of: " + ", ".join(_ROW_CONTAINER_KEYS)
            )
    else:
        raise CandidateCheckError("CFSM JSON root must be an object or array")

    mappings = [row for row in rows if isinstance(row, dict)]
    if not mappings:
        raise CandidateCheckError("CFSM JSON contains no song rows")
    return mappings


def load_cfsm_catalog(path: Path) -> tuple[tuple[CatalogSong, ...], str, str]:
    """Read a CFSM JSON export without modifying it or the Rocksmith installation."""

    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"CFSM catalog not found: {path}")

    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateCheckError(f"CFSM catalog is not valid UTF-8 JSON: {exc}") from exc

    songs: list[CatalogSong] = []
    for row in _extract_rows(payload):
        artist = _first_text(row, _ARTIST_KEYS)
        title = _first_text(row, _TITLE_KEYS)
        if artist is None or title is None:
            continue
        songs.append(
            CatalogSong(
                artist=artist,
                title=title,
                arrangements=_first_metadata(row, _ARRANGEMENT_KEYS),
                tunings=_first_metadata(row, _TUNING_KEYS),
                library_kind=_library_kind(row),
            )
        )

    if not songs:
        raise CandidateCheckError(
            "No rows contained recognizable artist/title fields; export those columns from CFSM"
        )

    digest = hashlib.sha256(raw).hexdigest()
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return tuple(songs), digest, modified


def _ordered_counts(values: list[str]) -> dict[str, int]:
    counts = Counter(values)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], _identity_key(item[0]), item[0].casefold()))
    return dict(ordered)


def summarize_catalog(catalog_path: Path) -> LibrarySummary:
    """Return a deterministic read-only summary of a local CFSM metadata export."""

    songs, digest, modified = load_cfsm_catalog(catalog_path)
    unique_artists = {_identity_key(song.artist) for song in songs}
    unique_songs = {(_identity_key(song.artist), _identity_key(song.title)) for song in songs}

    kind_counts_raw = Counter(song.library_kind for song in songs)
    kind_counts = {
        "official_dlc": kind_counts_raw.get("official_dlc", 0),
        "custom_or_local": kind_counts_raw.get("custom_or_local", 0),
        "unknown": kind_counts_raw.get("unknown", 0),
    }
    arrangements = [arrangement for song in songs for arrangement in song.arrangements]
    tunings = [tuning for song in songs for tuning in song.tunings]

    return LibrarySummary(
        catalog_path=catalog_path.expanduser().resolve(),
        catalog_sha256=digest,
        catalog_modified_utc=modified,
        row_count=len(songs),
        unique_artist_count=len(unique_artists),
        unique_song_count=len(unique_songs),
        library_kind_counts=kind_counts,
        arrangement_counts=_ordered_counts(arrangements),
        tuning_counts=_ordered_counts(tunings),
    )


def check_candidate(catalog_path: Path, *, artist: str, title: str) -> CandidateCheckResult:
    if not artist.strip() or not title.strip():
        raise CandidateCheckError("artist and title must be non-empty")

    songs, digest, modified = load_cfsm_catalog(catalog_path)
    artist_exact = artist.strip().casefold()
    title_exact = title.strip().casefold()
    artist_norm = normalize_name(artist)
    title_norm = normalize_name(title)

    exact = tuple(
        song
        for song in songs
        if song.artist.casefold() == artist_exact and song.title.casefold() == title_exact
    )
    normalized = tuple(
        song
        for song in songs
        if normalize_name(song.artist) == artist_norm and normalize_name(song.title) == title_norm
    )
    same_artist = tuple(song for song in songs if normalize_name(song.artist) == artist_norm)

    if len(normalized) > len(exact):
        match_type = "normalized" if len(normalized) == 1 else "ambiguous_normalized"
        matches = normalized
    elif exact:
        match_type = "exact" if len(exact) == 1 else "ambiguous_exact"
        matches = exact
    elif normalized:
        match_type = "normalized" if len(normalized) == 1 else "ambiguous_normalized"
        matches = normalized
    else:
        match_type = "none"
        matches = ()

    return CandidateCheckResult(
        artist=artist.strip(),
        title=title.strip(),
        match_type=match_type,
        catalog_path=catalog_path.expanduser().resolve(),
        catalog_sha256=digest,
        catalog_modified_utc=modified,
        matches=matches,
        same_artist=same_artist,
    )
