from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1
TIERS = frozenset(
    {
        "tier_1_mvp",
        "tier_2_generalization",
        "tier_3_advanced",
        "tier_4_stress",
        "reserve",
    }
)
STRUCTURED_REFERENCE_STATUSES = frozenset(
    {"verified_strong", "verified_good", "provisional"}
)
DLC_LIBRARY_STATUSES = frozenset(
    {"manual_search_no_exact_match", "requires_full_cfsm_check"}
)
REQUIRED_CANDIDATE_FIELDS = frozenset(
    {
        "rank",
        "benchmark_id",
        "artist",
        "title",
        "tier",
        "role",
        "structured_reference",
        "dlc_library",
        "rationale",
    }
)
BENCHMARK_ID_RE = re.compile(r"^BMARK-[0-9]{3}$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
FORBIDDEN_ASSET_SUFFIXES = frozenset(
    {
        ".psarc",
        ".wem",
        ".bnk",
        ".ogg",
        ".wav",
        ".mp3",
        ".flac",
        ".m4a",
        ".aac",
        ".gp",
        ".gp3",
        ".gp4",
        ".gp5",
        ".gpx",
        ".mid",
        ".midi",
        ".musicxml",
        ".mxl",
        ".xml",
        ".json",
        ".rs2dlc",
    }
)
TOKEN_RE = re.compile(r"[^\s\"'(),;<>]+")


class BenchmarkCandidateValidationError(ValueError):
    """Raised when committed benchmark candidate metadata violates the trusted contract."""


@dataclass(frozen=True)
class BenchmarkCandidateValidationResult:
    path: Path
    candidate_count: int
    ranks: tuple[int, ...]
    benchmark_ids: tuple[str, ...]


def _require_non_empty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkCandidateValidationError(f"{label} must be a non-empty string")
    return value


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkCandidateValidationError(f"{label} must be a mapping")
    return value


def _require_enum(value: Any, *, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise BenchmarkCandidateValidationError(f"{label} is not an allowed value")
    return value


def _walk_strings(value: Any, *, location: str = "root") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(_walk_strings(child, location=f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_strings(child, location=f"{location}[{index}]"))
    elif isinstance(value, str):
        found.append((location, value))
    return found


def _iter_metadata_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(text):
        token = raw.strip("[]{}.")
        if token:
            tokens.append(token)
    return tokens


def _looks_like_unsafe_path(token: str) -> bool:
    lowered = token.lower()
    if lowered.startswith("file://"):
        return True
    if WINDOWS_ABSOLUTE_RE.match(token) or token.startswith("\\\\") or token.startswith("/"):
        return True
    if lowered.startswith("https://") or lowered.startswith("http://"):
        return False

    path_portion = token.split("?", 1)[0].split("#", 1)[0].rstrip(":")
    return Path(path_portion).suffix.lower() in FORBIDDEN_ASSET_SUFFIXES


def _reject_asset_paths(payload: dict[str, Any]) -> None:
    for location, text in _walk_strings(payload):
        for token in _iter_metadata_tokens(text):
            if _looks_like_unsafe_path(token):
                raise BenchmarkCandidateValidationError(
                    "Local/commercial/generated asset path is not allowed in committed "
                    f"benchmark metadata: {location}"
                )


def validate_candidate_bank_data(
    payload: Any,
    *,
    source_path: Path = Path("<memory>"),
) -> BenchmarkCandidateValidationResult:
    root = _require_mapping(payload, label="Candidate bank root")

    schema_version = root.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != SCHEMA_VERSION
    ):
        raise BenchmarkCandidateValidationError(
            f"Candidate bank schema_version must be integer {SCHEMA_VERSION}"
        )

    _require_non_empty_string(root.get("purpose"), label="purpose")
    _require_mapping(root.get("promotion_policy"), label="promotion_policy")

    updated_at = root.get("updated_at")
    if updated_at is not None and not isinstance(updated_at, str):
        raise BenchmarkCandidateValidationError("updated_at must be a string or null")

    candidates = root.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise BenchmarkCandidateValidationError("candidates must be a non-empty list")

    ranks: list[int] = []
    benchmark_ids: list[str] = []

    for index, raw_candidate in enumerate(candidates):
        label = f"candidates[{index}]"
        candidate = _require_mapping(raw_candidate, label=label)

        missing = sorted(REQUIRED_CANDIDATE_FIELDS - candidate.keys())
        if missing:
            raise BenchmarkCandidateValidationError(
                f"{label} is missing required fields: {', '.join(missing)}"
            )

        rank = candidate["rank"]
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            raise BenchmarkCandidateValidationError(
                f"{label}.rank must be a positive integer"
            )
        ranks.append(rank)

        benchmark_id = _require_non_empty_string(
            candidate["benchmark_id"], label=f"{label}.benchmark_id"
        )
        if not BENCHMARK_ID_RE.fullmatch(benchmark_id):
            raise BenchmarkCandidateValidationError(
                f"{label}.benchmark_id must match BMARK-NNN"
            )
        benchmark_ids.append(benchmark_id)

        for field in ("artist", "title", "role", "rationale"):
            _require_non_empty_string(candidate[field], label=f"{label}.{field}")

        duration = candidate.get("duration_seconds")
        if duration is not None:
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(duration)
                or duration <= 0
            ):
                raise BenchmarkCandidateValidationError(
                    f"{label}.duration_seconds must be finite and positive when known"
                )

        _require_enum(candidate["tier"], allowed=TIERS, label=f"{label}.tier")

        structured = _require_mapping(
            candidate["structured_reference"],
            label=f"{label}.structured_reference",
        )
        _require_enum(
            structured.get("status"),
            allowed=STRUCTURED_REFERENCE_STATUSES,
            label=f"{label}.structured_reference.status",
        )
        _require_non_empty_string(
            structured.get("kind"), label=f"{label}.structured_reference.kind"
        )

        dlc_library = _require_mapping(
            candidate["dlc_library"], label=f"{label}.dlc_library"
        )
        _require_enum(
            dlc_library.get("status"),
            allowed=DLC_LIBRARY_STATUSES,
            label=f"{label}.dlc_library.status",
        )

    if len(set(ranks)) != len(ranks):
        raise BenchmarkCandidateValidationError("Candidate ranks must be unique")
    if len(set(benchmark_ids)) != len(benchmark_ids):
        raise BenchmarkCandidateValidationError(
            "Candidate benchmark_id values must be unique"
        )

    _reject_asset_paths(root)

    return BenchmarkCandidateValidationResult(
        path=source_path,
        candidate_count=len(candidates),
        ranks=tuple(ranks),
        benchmark_ids=tuple(benchmark_ids),
    )


def validate_candidate_bank(path: Path) -> BenchmarkCandidateValidationResult:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Candidate bank not found: {path}")

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise BenchmarkCandidateValidationError(
            f"Candidate bank YAML is invalid: {exc}"
        ) from exc

    return validate_candidate_bank_data(payload, source_path=path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate benchmark candidate-bank metadata"
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("benchmarks/candidate_bank.yaml"),
    )
    args = parser.parse_args()

    try:
        result = validate_candidate_bank(args.path)
    except (BenchmarkCandidateValidationError, FileNotFoundError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")

    print(
        f"PASS: {result.candidate_count} benchmark candidates validated: {result.path}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
