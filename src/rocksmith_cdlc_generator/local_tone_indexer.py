from __future__ import annotations

from pathlib import Path

from .local_psarc_workspace import VerifiedPsarcCopy, copy_psarc_for_inspection
from .private_psarc_extraction import PrivatePsarcExtraction, extract_verified_psarc
from .tone_manifest_parser import parse_tone_manifest_file
from .tone_reference_library import (
    ReferenceSource,
    ToneReferenceLibrary,
    merge_scan_results,
    read_library,
    write_library,
)


def parse_private_extraction(
    extraction: PrivatePsarcExtraction,
    *,
    verified: VerifiedPsarcCopy,
    source_type: ReferenceSource,
) -> list:
    """Convert verified private extraction candidates into normalized tone references.

    Only JSON candidates reported inside the verified extraction directory are parsed.
    Malformed/unsupported manifests contribute no records rather than guessed data.
    """
    if not verified.verified:
        raise ValueError("unverified PSARC copies cannot populate the tone library")
    if extraction.source_sha256 != verified.source_sha256:
        raise ValueError("extraction receipt does not match the verified PSARC SHA-256")
    if Path(extraction.verified_copy).resolve() != verified.copy.resolve():
        raise ValueError("extraction receipt does not match the verified private copy")

    extracted_root = Path(extraction.extracted_directory).resolve()
    records = []
    for raw_path in extraction.tone_json_candidates:
        path = Path(raw_path).resolve()
        if not path.is_relative_to(extracted_root):
            raise ValueError("tone manifest candidate escaped the private extraction directory")
        if not path.is_file():
            continue
        try:
            records.extend(
                parse_tone_manifest_file(
                    path,
                    source_psarc_sha256=verified.source_sha256,
                    source_path=str(verified.source.resolve()),
                    source_type=source_type,
                )
            )
        except (OSError, UnicodeError, ValueError):
            # Candidate discovery is intentionally broad. Unsupported or malformed JSON
            # is ignored rather than transformed into speculative tone data.
            continue
    return records


def merge_private_extraction(
    extraction: PrivatePsarcExtraction,
    *,
    verified: VerifiedPsarcCopy,
    source_type: ReferenceSource,
    dlc_root: Path,
    existing: ToneReferenceLibrary | None = None,
) -> ToneReferenceLibrary:
    tones = parse_private_extraction(extraction, verified=verified, source_type=source_type)
    return merge_scan_results(
        dlc_root,
        [(verified.source, source_type, tones)],
        existing=existing,
    )


def index_local_psarc(
    source: Path,
    *,
    dlc_root: Path,
    rocksmith_root: Path,
    workspace_root: Path,
    library_path: Path,
    source_type: ReferenceSource,
    bridge_path: Path | None = None,
) -> ToneReferenceLibrary:
    """Stage, extract, parse, and merge one installed PSARC without modifying it."""
    verified = copy_psarc_for_inspection(
        source,
        workspace_root=workspace_root,
        rocksmith_root=rocksmith_root,
    )
    extraction = extract_verified_psarc(
        verified,
        workspace_root=workspace_root,
        rocksmith_root=rocksmith_root,
        bridge_path=bridge_path,
    )
    existing = read_library(library_path) if library_path.is_file() else None
    updated = merge_private_extraction(
        extraction,
        verified=verified,
        source_type=source_type,
        dlc_root=dlc_root,
        existing=existing,
    )
    return write_library(updated, library_path) and updated
