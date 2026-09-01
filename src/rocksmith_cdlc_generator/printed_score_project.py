from __future__ import annotations

import json
from pathlib import Path
import shutil
import wave

from .hashing import sha256_file
from .models import AudioMetadata, ProjectManifest
from .private_score_bundle import (
    PrivateScoreBundleSpec,
    PrivateScoreMovementSpec,
    register_private_score_bundle,
    registered_manifest_path,
)
from .project import slugify


_BOOTSTRAP_SAMPLE_RATE = 44_100
_BOOTSTRAP_SECONDS = 1
_BOOTSTRAP_FILENAME = "printed-score-bootstrap-silence.wav"
_AUTHORITY_FILENAME = "printed-score-project.json"


class PrintedScoreProjectError(ValueError):
    pass


def _movement(spec: PrivateScoreBundleSpec, movement_id: str | None) -> PrivateScoreMovementSpec:
    if movement_id is None:
        return spec.movements[0]
    for movement in spec.movements:
        if movement.movement_id == movement_id:
            return movement
    available = ", ".join(item.movement_id for item in spec.movements)
    raise PrintedScoreProjectError(
        f"movement {movement_id!r} is not in {spec.bundle_id}; available: {available}"
    )


def printed_score_project_authority_path(project_dir: Path) -> Path:
    return Path(project_dir).expanduser().resolve() / _AUTHORITY_FILENAME


def read_printed_score_project_authority(project_dir: Path) -> dict[str, object]:
    path = printed_score_project_authority_path(project_dir)
    if not path.is_file():
        raise PrintedScoreProjectError(f"printed-score project authority is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise PrintedScoreProjectError("unsupported printed-score project authority schema")
    return payload


def _write_silent_bootstrap_wav(path: Path) -> None:
    """Write a tiny valid local WAV so legacy recording-oriented shell code stays safe.

    This WAV is *not* musical authority and is never used to derive score timing. The
    reviewed printed notation later produces its own deterministic click/tempo clock.
    It exists only because the original ProjectManifest predates score-only projects
    and several mature desktop/readiness paths still expect a valid audio-shaped
    project source to exist while the new source-mode model is introduced incrementally.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = _BOOTSTRAP_SAMPLE_RATE * _BOOTSTRAP_SECONDS
    silence = b"\x00\x00" * frame_count
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(_BOOTSTRAP_SAMPLE_RATE)
        handle.writeframes(silence)


def is_printed_score_project(project_dir: Path) -> bool:
    root = Path(project_dir).expanduser().resolve()
    return (
        (root / "project.json").is_file()
        and registered_manifest_path(root).is_file()
        and printed_score_project_authority_path(root).is_file()
    )


def create_printed_score_project(
    *,
    spec_path: Path,
    source_dir: Path,
    projects_root: Path,
    movement_id: str | None = None,
) -> Path:
    """Create a desktop-openable project around a private printed-score bundle.

    All copyrighted page images remain in the project's ignored private reference
    directory. The committed/public YAML is only a metadata + expected-hash contract.
    Registration must succeed completely before the project is retained.
    """

    spec_file = Path(spec_path).expanduser().resolve()
    source_root = Path(source_dir).expanduser().resolve()
    projects_root = Path(projects_root).expanduser().resolve()
    if not spec_file.is_file():
        raise FileNotFoundError(spec_file)
    if not source_root.is_dir():
        raise NotADirectoryError(source_root)

    spec = PrivateScoreBundleSpec.read_yaml(spec_file)
    if spec.instrument.strip().lower() != "bass":
        raise PrintedScoreProjectError(
            "printed-score project authoring currently supports Bass only; "
            f"manifest instrument is {spec.instrument!r}"
        )
    movement = _movement(spec, movement_id)
    display_title = f"{spec.work_title} — {movement.title}"
    project_name = f"{spec.composer} - {display_title}"
    project_dir = projects_root / slugify(project_name)
    project_dir = project_dir.resolve()
    if project_dir.exists():
        raise FileExistsError(f"Project already exists: {project_dir}")

    standard_dirs = (
        "source",
        "audio",
        "stems",
        "analysis",
        "charts",
        "review",
        "eof",
        "build",
        "derived",
    )

    try:
        for relative in standard_dirs:
            (project_dir / relative).mkdir(parents=True, exist_ok=True)

        bootstrap_audio = project_dir / "source" / _BOOTSTRAP_FILENAME
        _write_silent_bootstrap_wav(bootstrap_audio)
        bootstrap_sha256 = sha256_file(bootstrap_audio)

        manifest = ProjectManifest(
            project_name=project_name,
            artist=spec.composer,
            title=display_title,
            arrangement_instruments=[spec.instrument],
            source_original_path=str(spec_file),
            source_project_path=bootstrap_audio.relative_to(project_dir).as_posix(),
            source_sha256=bootstrap_sha256,
            source_metadata=AudioMetadata(
                duration_seconds=float(_BOOTSTRAP_SECONDS),
                sample_rate_hz=_BOOTSTRAP_SAMPLE_RATE,
                channels=1,
                codec_name="pcm_s16le",
                format_name="printed-score-bootstrap-silence",
            ),
        )
        manifest.save(project_dir)

        registered = register_private_score_bundle(project_dir, spec_file, source_root)
        if registered.bundle_id != spec.bundle_id:
            raise PrintedScoreProjectError("registered private score identity changed unexpectedly")
        if not registered_manifest_path(project_dir).is_file():
            raise PrintedScoreProjectError("private score registration did not produce its manifest")

        authority = {
            "schema_version": 1,
            "bundle_id": spec.bundle_id,
            "instrument": spec.instrument,
            "movement_id": movement.movement_id,
            "movement_title": movement.title,
            "start_page": movement.start_page,
            "end_page": movement.end_page,
        }
        printed_score_project_authority_path(project_dir).write_text(
            json.dumps(authority, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise

    return project_dir
