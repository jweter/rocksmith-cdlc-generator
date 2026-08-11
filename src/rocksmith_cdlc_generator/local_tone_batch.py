from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from .local_tone_indexer import index_local_psarc
from .tone_reference_library import (
    ReferenceSource,
    ToneReferenceLibrary,
    changed_psarcs,
    read_library,
)


class BatchPackageResult(BaseModel):
    path: str
    status: str
    source_type: ReferenceSource
    tone_count_after: int | None = None
    error_type: str | None = None
    error_message: str | None = None


class BatchScanReport(BaseModel):
    schema_version: int = 1
    dlc_root: str
    library_path: str
    planned_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: list[BatchPackageResult] = Field(default_factory=list)


SourceResolver = Callable[[Path], ReferenceSource]


def load_explicit_source_map(path: Path | None) -> dict[str, ReferenceSource]:
    """Load an operator-authored exact-path authority map.

    The scanner never infers official/custom authority from a package filename.
    Keys may be absolute paths or paths relative to the DLC root; normalization is
    performed by ``source_resolver_from_map``.
    """
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("source map must be a JSON object of path -> source type")
    allowed = {"official_rocksmith", "custom_dlc", "user_created", "unknown"}
    result: dict[str, ReferenceSource] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or value not in allowed:
            raise ValueError("source map contains an invalid path or source type")
        result[key] = value
    return result


def source_resolver_from_map(
    dlc_root: Path,
    mapping: dict[str, ReferenceSource],
    *,
    default: ReferenceSource = "unknown",
) -> SourceResolver:
    root = dlc_root.resolve()
    normalized: dict[Path, ReferenceSource] = {}
    for raw_path, source_type in mapping.items():
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("source-map path escaped the configured DLC root")
        normalized[resolved] = source_type

    def resolve(path: Path) -> ReferenceSource:
        return normalized.get(path.resolve(), default)

    return resolve


def scan_changed_psarcs(
    *,
    dlc_root: Path,
    rocksmith_root: Path,
    workspace_root: Path,
    library_path: Path,
    source_resolver: SourceResolver,
    bridge_path: Path | None = None,
    limit: int | None = None,
) -> BatchScanReport:
    """Incrementally index changed packages with per-package failure isolation.

    Each successful package is persisted immediately by ``index_local_psarc``. A
    later failure therefore cannot erase earlier progress, and failed packages
    remain absent/changed so a subsequent run naturally retries them.
    """
    existing: ToneReferenceLibrary | None = read_library(library_path) if library_path.is_file() else None
    planned = changed_psarcs(dlc_root, existing)
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        planned = planned[:limit]

    results: list[BatchPackageResult] = []
    for source in planned:
        source_type = source_resolver(source)
        try:
            library = index_local_psarc(
                source,
                dlc_root=dlc_root,
                rocksmith_root=rocksmith_root,
                workspace_root=workspace_root,
                library_path=library_path,
                source_type=source_type,
                bridge_path=bridge_path,
            )
            package = next((item for item in library.psarcs if Path(item.path).resolve() == source.resolve()), None)
            results.append(
                BatchPackageResult(
                    path=str(source.resolve()),
                    status="indexed",
                    source_type=source_type,
                    tone_count_after=package.tone_count if package else 0,
                )
            )
        except Exception as exc:  # package isolation is intentional at this boundary
            results.append(
                BatchPackageResult(
                    path=str(source.resolve()),
                    status="failed",
                    source_type=source_type,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

    succeeded = sum(item.status == "indexed" for item in results)
    failed = sum(item.status == "failed" for item in results)
    return BatchScanReport(
        dlc_root=str(dlc_root.resolve()),
        library_path=str(library_path.resolve()),
        planned_count=len(planned),
        succeeded_count=succeeded,
        failed_count=failed,
        results=results,
    )


def write_batch_report(report: BatchScanReport, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return destination
