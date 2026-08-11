from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from .local_tone_batch import BatchScanReport, SourceResolver, scan_changed_psarcs
from .tone_corpus_diagnostics import ToneCorpusStats, summarize_library
from .tone_reference_library import ToneReferenceLibrary, read_library


class FirstScanPreflight(BaseModel):
    dlc_root: str
    rocksmith_root: str
    workspace_root: str
    library_path: str
    package_limit: int = Field(ge=1, le=25)


class FirstScanReport(BaseModel):
    schema_version: int = 1
    preflight: FirstScanPreflight
    batch: BatchScanReport
    corpus: dict[str, object]


def validate_first_scan_paths(
    *,
    dlc_root: Path,
    rocksmith_root: Path,
    workspace_root: Path,
    library_path: Path,
    package_limit: int,
) -> FirstScanPreflight:
    if not 1 <= package_limit <= 25:
        raise ValueError("first-scan package limit must be between 1 and 25")
    root = rocksmith_root.resolve()
    dlc = dlc_root.resolve()
    workspace = workspace_root.resolve()
    library = library_path.resolve()
    if not dlc.is_relative_to(root):
        raise ValueError("DLC root must be inside the configured Rocksmith installation")
    if workspace.is_relative_to(root):
        raise ValueError("private workspace must be outside the live Rocksmith installation")
    if library.is_relative_to(root):
        raise ValueError("private library must be outside the live Rocksmith installation")
    if not dlc.is_dir():
        raise FileNotFoundError(f"DLC root does not exist: {dlc}")
    return FirstScanPreflight(
        dlc_root=str(dlc),
        rocksmith_root=str(root),
        workspace_root=str(workspace),
        library_path=str(library),
        package_limit=package_limit,
    )


def run_controlled_first_scan(
    *,
    dlc_root: Path,
    rocksmith_root: Path,
    workspace_root: Path,
    library_path: Path,
    source_resolver: SourceResolver,
    package_limit: int = 5,
    bridge_path: Path | None = None,
    scan_fn: Callable[..., BatchScanReport] = scan_changed_psarcs,
) -> FirstScanReport:
    preflight = validate_first_scan_paths(
        dlc_root=dlc_root,
        rocksmith_root=rocksmith_root,
        workspace_root=workspace_root,
        library_path=library_path,
        package_limit=package_limit,
    )
    batch = scan_fn(
        dlc_root=dlc_root,
        rocksmith_root=rocksmith_root,
        workspace_root=workspace_root,
        library_path=library_path,
        source_resolver=source_resolver,
        bridge_path=bridge_path,
        limit=package_limit,
    )
    library: ToneReferenceLibrary = (
        read_library(library_path)
        if library_path.is_file()
        else ToneReferenceLibrary(scan_root=str(dlc_root.resolve()))
    )
    stats: ToneCorpusStats = summarize_library(library)
    return FirstScanReport(preflight=preflight, batch=batch, corpus=asdict(stats))


def write_first_scan_report(report: FirstScanReport, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
    return destination
