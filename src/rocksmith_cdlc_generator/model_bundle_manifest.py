"""Strict local model bundle manifest; bytes never leave the owner's cache.

A complete list with correct hashes proves the *declared* dependencies exist,
not that an upstream loader cannot request undeclared files or network access.
Model licensing and Windows network isolation remain independent gates.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re

from .hashing import sha256_file

_HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_FILES = 64
MAX_MANIFEST_BYTES = 128 * 1024


@dataclass(frozen=True)
class ModelBundleAttestation:
    status: str
    code: str
    manifest_sha256: str | None = None
    model_sha256: str | None = None
    verified_file_count: int = 0
    dependency_closure_proven: bool = False
    license_verified: bool = False
    network_isolation_proven: bool = False


def inspect_cached_model_bundle(
    cache_dir: Path,
    manifest_path: Path | None,
    *,
    model_filename: str,
    expected_model_sha256: str | None,
) -> ModelBundleAttestation:
    """Verify each listed local regular file, rejecting traversal and symlinks.

    The manifest must itself live directly in the explicitly chosen cache
    directory. The result contains only hashes/status, never a local path.
    """
    def blocked(code: str) -> ModelBundleAttestation:
        return ModelBundleAttestation("BLOCKED", code)
    if manifest_path is None:
        return blocked("MODEL_MANIFEST_REQUIRED")
    cache = Path(cache_dir).resolve()
    candidate = Path(manifest_path)
    if candidate.is_symlink():
        return blocked("MODEL_MANIFEST_SYMLINK")
    manifest = candidate.resolve()
    if (manifest.parent != cache or manifest.suffix.lower() != ".json"
            or not manifest.is_file()):
        return blocked("MODEL_MANIFEST_OUTSIDE_CACHE")
    try:
        if not 1 <= manifest.stat().st_size <= MAX_MANIFEST_BYTES:
            return blocked("MODEL_MANIFEST_SIZE_INVALID")
        raw = manifest.read_bytes()
        data = json.loads(raw)
    except (OSError, UnicodeError, ValueError):
        return blocked("MODEL_MANIFEST_INVALID")
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return blocked("MODEL_MANIFEST_SCHEMA_INVALID")
    if data.get("model_filename") != model_filename:
        return blocked("MODEL_MANIFEST_MODEL_MISMATCH")
    entries = data.get("files")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FILES:
        return blocked("MODEL_MANIFEST_FILE_COUNT_INVALID")
    if expected_model_sha256 is None or not _HEX.fullmatch(expected_model_sha256):
        return blocked("MODEL_SHA256_PIN_REQUIRED")

    seen: set[str] = set()
    found_model = False
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size_bytes"}:
            return blocked("MODEL_MANIFEST_ENTRY_INVALID")
        relative, digest, length = (entry["path"], entry["sha256"], entry["size_bytes"])
        if (
            not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative or "\x00" in relative or len(relative) > 240
        ):
            return blocked("MODEL_MANIFEST_PATH_INVALID")
        rel = PurePosixPath(relative)
        if (rel.is_absolute() or any(part in {"", ".", ".."} for part in relative.split("/"))
                or any(part.startswith(".") for part in rel.parts)):
            return blocked("MODEL_MANIFEST_PATH_INVALID")
        if relative in seen:
            return blocked("MODEL_MANIFEST_DUPLICATE_PATH")
        seen.add(relative)
        if (not isinstance(digest, str) or not _HEX.fullmatch(digest)
                or type(length) is not int or length <= 0 or length > 20 * 1024**3):
            return blocked("MODEL_MANIFEST_ENTRY_INVALID")
        path = cache.joinpath(*rel.parts)
        if not path.resolve().is_relative_to(cache):
            return blocked("MODEL_MANIFEST_PATH_ESCAPES_CACHE")
        # Any symlink in the prefix is prohibited, including one that still
        # resolves inside the cache, so an attacker cannot swap targets.
        check = cache
        for part in rel.parts:
            check = check / part
            if check.is_symlink():
                return blocked("MODEL_MANIFEST_SYMLINK")
        try:
            if not path.is_file() or path.stat().st_size != length or sha256_file(path) != digest:
                return blocked("MODEL_MANIFEST_CONTENT_MISMATCH")
        except (OSError, ValueError):
            return blocked("MODEL_MANIFEST_CONTENT_UNREADABLE")
        if relative == model_filename:
            found_model = True
            if digest != expected_model_sha256:
                return blocked("MODEL_MANIFEST_MODEL_MISMATCH")
    if not found_model:
        return blocked("MODEL_MANIFEST_PRIMARY_MODEL_MISSING")
    return ModelBundleAttestation(
        "VERIFIED_DECLARED_FILES", "MANIFEST_DECLARED_FILES_VERIFIED",
        manifest_sha256=sha256_file(manifest),
        model_sha256=expected_model_sha256,
        verified_file_count=len(entries),
        # A manifest cannot prove an upstream audio-separator loader's full
        # dependency closure, licensing, network sandbox or separator quality.
    )
