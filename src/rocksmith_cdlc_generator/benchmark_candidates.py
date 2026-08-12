from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SCHEMA_VERSION = 1
TIERS = {
    "tier_1_mvp",
    "tier_2_generalization",
    "tier_3_advanced",
    "tier_4_stress",
    "reserve",
}
STRUCTURED_REFERENCE_STATUSES = {"verified_strong", "verified_good", "provisional"}
DLC_LIBRARY_STATUSES = {"manual_search_no_exact_match", "requires_full_cfsm_check"}
REQUIRED_CANDIDATE_FIELDS = {
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
BENCHMARK_ID_RE = re.compile(r"^BMARK-[0-9]{3}$")
ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")
COMMERCIAL_ASSET_RE = re.compile(
    r"(?:^|[\\/\s'\"(])[^\s'\")]*\.(?:psarc|wem|bnk|ogg|wav|mp3|flac|m4a|aac|gp|gp3|gp4|gp5|gpx|mid|midi)(?:$|[\s'\"),])",
    re.IGNORECASE,
)


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


def _reject_asset_paths(payload: dict[str, Any]) -> None:
    for location, text in _walk_strings(payload):
        stripped = text.strip()
        if ABSOLUTE_PATH_RE.match(stripped):
            raise BenchmarkCandidateValidationError(
                f"Local absolute path is not allowed in committed benchmark metadata: {location}"
            )
        if stripped.lower().startswith("file://"):
            raise BenchmarkCandidateValidationError(
                f"Local file URI is not allowed in committed benchmark metadata: {location}"
            )
        if COMMERCIAL_ASSET_RE.search(stripped):
            raise BenchmarkCandidateValidationError(
                f"Commercial/generated asset path is not allowed in committed benchmark metadata: {location}"
            )


def validate_candidate_bank_data(
    payload: Any,
    *,
    source_path: Path = Path("<memory>"),
) -> BenchmarkCandidateValidationResult:
    if not isinstance(payload, dict):
        raise BenchmarkCandidateValidationError("Candidate bank root must be a mapping")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkCandidateValidationError(
            f"Candidate bank schema_version must be {SCHEMA_VERSION}"
        )

    _require_non_empty_string(payload.get("purpose"), label="purpose")
    if not isinstance(payload.get("promotion_policy"), dict):
        raise BenchmarkCandidateValidationError("promotion_policy must be a mapping")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise BenchmarkCandidateValidationError("candidates must be a non-empty list")

    ranks: list[int] = []
    benchmark_ids: list[str] = []
    for index, candidate in enumerate(candidates):
        label = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            raise BenchmarkCandidateValidationError(f"{label} must be a mapping")
        missing = sorted(REQUIRED_CANDIDATE_FIELDS - candidate.keys())
        if missing:
            raise BenchmarkCandidateValidationError(
                f"{label} is missing required fields: {', '.join(missing)}"
            )

        rank = candidate["rank"]
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            raise BenchmarkCandidateValidationError(f"{label}.rank must be a positive integer")
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
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
                raise BenchmarkCandidateValidationError(
                    f"{label}.duration_seconds must be positive when known"
                )

        if candidate["tier"] not in TIERS:
            raise BenchmarkCandidateValidationError(f"{label}.tier is not an allowed value")

        structured = candidate["structured_reference"]
        if not isinstance(structured, dict):
            raise BenchmarkCandidateValidationError(f"{label}.structured_reference must be a mapping")
        if structured.get("status") not in STRUCTURED_REFERENCE_STATUSES:
            raise BenchmarkCandidateValidationError(
                f"{label}.structured_reference.status is not an allowed value"
            )
        _require_non_empty_string(structured.get("kind"), label=f"{label}.structured_reference.kind")

        dlc_library = candidate["dlc_library"]
        if not isinstance(dlc_library, dict):
            raise BenchmarkCandidateValidationError(f"{label}.dlc_library must be a mapping")
        if dlc_library.get("status") not in DLC_LIBRARY_STATUSES:
            raise BenchmarkCandidateValidationError(
                f"{label}.dlc_library.status is not an allowed value"
            )

    if len(set(ranks)) != len(ranks):
        raise BenchmarkCandidateValidationError("Candidate ranks must be unique")
    if len(set(benchmark_ids)) != len(benchmark_ids):
        raise BenchmarkCandidateValidationError("Candidate benchmark_id values must be unique")

    _reject_asset_paths(payload)

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
        raise BenchmarkCandidateValidationError(f"Candidate bank YAML is invalid: {exc}") from exc
    return validate_candidate_bank_data(payload, source_path=path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark candidate-bank metadata")
    parser.add_argument("path", nargs="?", type=Path, default=Path("benchmarks/candidate_bank.yaml"))
    args = parser.parse_args()
    result = validate_candidate_bank(args.path)
    print(f"PASS: {result.candidate_count} benchmark candidates validated: {result.path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
