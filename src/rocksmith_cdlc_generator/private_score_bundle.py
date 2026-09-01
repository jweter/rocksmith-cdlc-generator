from __future__ import annotations

from pathlib import Path, PurePosixPath
import json
import re
import shutil
from typing import Literal

import yaml
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file


REGISTERED_MANIFEST_RELATIVE_PATH = Path("references") / "printed-score" / "manifest.json"
REGISTERED_PAGES_RELATIVE_PATH = Path("references") / "printed-score" / "pages"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}

PageKind = Literal["contents", "score", "legend"]


class PrivateScoreBundleError(ValueError):
    pass


class PrivateScorePageSpec(BaseModel):
    """Metadata for one private page image that must remain outside the public repo."""

    model_config = ConfigDict(frozen=True)

    source_filename: str = Field(min_length=1)
    kind: PageKind
    printed_page: int | None = Field(default=None, ge=1)
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    note: str | None = None

    @model_validator(mode="after")
    def validate_page_identity(self) -> "PrivateScorePageSpec":
        pure = PurePosixPath(self.source_filename.replace("\\", "/"))
        if pure.is_absolute() or len(pure.parts) != 1 or ".." in pure.parts:
            raise ValueError("private score source_filename must be a plain filename")
        if self.kind == "score" and self.printed_page is None:
            raise ValueError("score pages require printed_page")
        return self


class PrivateScoreMovementSpec(BaseModel):
    """One movement/section boundary used to split a multi-page score into practice units."""

    model_config = ConfigDict(frozen=True)

    movement_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    title: str = Field(min_length=1)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    time_signature: str | None = None
    practice_bpm: float | None = Field(default=None, gt=0)
    navigation_note: str | None = None

    @model_validator(mode="after")
    def validate_page_range(self) -> "PrivateScoreMovementSpec":
        if self.end_page < self.start_page:
            raise ValueError("movement end_page must be >= start_page")
        return self


class PrivateScoreBundleSpec(BaseModel):
    """Public-safe metadata for a local copyrighted printed-score source set.

    The YAML spec may be committed because it contains only bibliographic metadata,
    page ordering, hashes, and workflow hints. The actual images remain local/private.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    bundle_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    work_title: str = Field(min_length=1)
    composer: str = Field(min_length=1)
    arrangement_title: str | None = None
    arranger: str | None = None
    publisher: str | None = None
    copyright_year: int | None = Field(default=None, ge=1)
    isbn: str | None = None
    instrument: Literal["bass", "lead", "rhythm"]
    tuning_name: str = Field(min_length=1)
    tuning_midi: list[int] = Field(min_length=1)
    source_rights_class: str = "user_owned_local"
    redistribution_allowed: bool = False
    pages: list[PrivateScorePageSpec] = Field(min_length=1)
    movements: list[PrivateScoreMovementSpec] = Field(min_length=1)
    notation_features: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bundle(self) -> "PrivateScoreBundleSpec":
        filenames = [page.source_filename for page in self.pages]
        if len(set(filenames)) != len(filenames):
            raise ValueError("private score source filenames must be unique")

        hashes = [page.expected_sha256 for page in self.pages if page.expected_sha256]
        if len(set(hashes)) != len(hashes):
            raise ValueError("private score expected_sha256 values must be unique")

        score_pages = [page.printed_page for page in self.pages if page.kind == "score"]
        if len(set(score_pages)) != len(score_pages):
            raise ValueError("private score printed score-page numbers must be unique")
        score_page_set = {page for page in score_pages if page is not None}

        movement_ids = [movement.movement_id for movement in self.movements]
        if len(set(movement_ids)) != len(movement_ids):
            raise ValueError("private score movement IDs must be unique")
        for movement in self.movements:
            missing = [
                page
                for page in range(movement.start_page, movement.end_page + 1)
                if page not in score_page_set
            ]
            if missing:
                raise ValueError(
                    f"movement {movement.movement_id} references missing score pages: {missing}"
                )
        return self

    @classmethod
    def read_yaml(cls, path: Path) -> "PrivateScoreBundleSpec":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(payload)


class RegisteredPrivateScorePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_filename: str
    kind: PageKind
    printed_page: int | None = None
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str | None = None

    @model_validator(mode="after")
    def validate_relative_path(self) -> "RegisteredPrivateScorePage":
        pure = PurePosixPath(self.relative_path.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError("registered private score page path must stay project-relative")
        return self


class RegisteredPrivateScoreBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    bundle_id: str
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    work_title: str
    composer: str
    arrangement_title: str | None = None
    arranger: str | None = None
    publisher: str | None = None
    copyright_year: int | None = None
    isbn: str | None = None
    instrument: Literal["bass", "lead", "rhythm"]
    tuning_name: str
    tuning_midi: list[int]
    source_rights_class: str
    redistribution_allowed: bool
    pages: list[RegisteredPrivateScorePage]
    movements: list[PrivateScoreMovementSpec]
    notation_features: list[str] = Field(default_factory=list)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "RegisteredPrivateScoreBundle":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def registered_manifest_path(project_dir: Path) -> Path:
    return Path(project_dir).resolve() / REGISTERED_MANIFEST_RELATIVE_PATH


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-")
    return cleaned or "score-page"


def _verify_image(path: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        raise PrivateScoreBundleError(f"unsupported printed-score image type: {path.name}")
    try:
        with Image.open(path) as image:
            image.seek(0)
            image.verify()
    except (OSError, SyntaxError) as exc:
        raise PrivateScoreBundleError(f"printed-score image cannot be decoded: {path.name}") from exc


def _project_file(project_dir: Path, relative_path: str) -> Path:
    root = Path(project_dir).resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise PrivateScoreBundleError("registered private score page escaped the project directory")
    return candidate


def register_private_score_bundle(
    project_dir: Path,
    spec_path: Path,
    source_dir: Path,
) -> RegisteredPrivateScoreBundle:
    """Copy and fingerprint a complete private multi-page score set into one project.

    This is deliberately a provenance/intake operation only. It does not recognize
    notation or promote any page into musical authority. The public spec identifies
    expected pages; this function keeps the copyrighted image bytes inside the local
    project and writes a hash-bound project manifest for future OMR/review stages.
    """

    project_root = Path(project_dir).expanduser().resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    spec_file = Path(spec_path).expanduser().resolve()
    source_root = Path(source_dir).expanduser().resolve()
    if not spec_file.is_file():
        raise FileNotFoundError(spec_file)
    if not source_root.is_dir():
        raise NotADirectoryError(source_root)

    spec = PrivateScoreBundleSpec.read_yaml(spec_file)
    spec_sha256 = sha256_file(spec_file)
    manifest_file = registered_manifest_path(project_root)
    if manifest_file.is_file():
        existing = RegisteredPrivateScoreBundle.read_json(manifest_file)
        if existing.bundle_id != spec.bundle_id:
            raise PrivateScoreBundleError(
                f"project already contains private score bundle {existing.bundle_id!r}"
            )
        if existing.source_manifest_sha256 != spec_sha256:
            raise PrivateScoreBundleError(
                "private score source manifest changed after registration; use a new project "
                "or explicitly preserve/reconcile the old provenance before replacing it"
            )

    pages_dir = project_root / REGISTERED_PAGES_RELATIVE_PATH
    pages_dir.mkdir(parents=True, exist_ok=True)
    registered_pages: list[RegisteredPrivateScorePage] = []

    for page in spec.pages:
        source = (source_root / page.source_filename).resolve()
        if not source.is_relative_to(source_root):
            raise PrivateScoreBundleError(f"source page escaped source directory: {page.source_filename}")
        if not source.is_file():
            raise FileNotFoundError(source)
        _verify_image(source)
        digest = sha256_file(source)
        if page.expected_sha256 is not None and digest != page.expected_sha256:
            raise PrivateScoreBundleError(
                f"hash mismatch for {page.source_filename}: expected {page.expected_sha256}, got {digest}"
            )

        destination = pages_dir / f"{digest[:12]}-{_safe_filename(page.source_filename)}"
        if not destination.exists():
            shutil.copy2(source, destination)
        _verify_image(destination)
        if sha256_file(destination) != digest:
            raise PrivateScoreBundleError(f"copied printed-score page hash mismatch: {page.source_filename}")

        registered_pages.append(
            RegisteredPrivateScorePage(
                source_filename=page.source_filename,
                kind=page.kind,
                printed_page=page.printed_page,
                relative_path=destination.relative_to(project_root).as_posix(),
                sha256=digest,
                note=page.note,
            )
        )

    registered = RegisteredPrivateScoreBundle(
        bundle_id=spec.bundle_id,
        source_manifest_sha256=spec_sha256,
        work_title=spec.work_title,
        composer=spec.composer,
        arrangement_title=spec.arrangement_title,
        arranger=spec.arranger,
        publisher=spec.publisher,
        copyright_year=spec.copyright_year,
        isbn=spec.isbn,
        instrument=spec.instrument,
        tuning_name=spec.tuning_name,
        tuning_midi=spec.tuning_midi,
        source_rights_class=spec.source_rights_class,
        redistribution_allowed=spec.redistribution_allowed,
        pages=registered_pages,
        movements=spec.movements,
        notation_features=spec.notation_features,
    )
    registered.write_json(manifest_file)
    return registered


def verify_private_score_bundle(project_dir: Path) -> RegisteredPrivateScoreBundle:
    """Verify every locally registered private page still exists and matches its hash."""

    project_root = Path(project_dir).expanduser().resolve()
    path = registered_manifest_path(project_root)
    if not path.is_file():
        raise FileNotFoundError(path)
    bundle = RegisteredPrivateScoreBundle.read_json(path)
    for page in bundle.pages:
        source = _project_file(project_root, page.relative_path)
        if not source.is_file():
            raise FileNotFoundError(source)
        _verify_image(source)
        digest = sha256_file(source)
        if digest != page.sha256:
            raise PrivateScoreBundleError(
                f"registered private score page changed after registration: {page.source_filename}"
            )
    return bundle


def movement_score_pages(
    bundle: RegisteredPrivateScoreBundle,
    movement_id: str,
) -> list[RegisteredPrivateScorePage]:
    """Return ordered score pages that contain one movement's source material."""

    movement = next((item for item in bundle.movements if item.movement_id == movement_id), None)
    if movement is None:
        raise KeyError(movement_id)
    pages = [
        page
        for page in bundle.pages
        if page.kind == "score"
        and page.printed_page is not None
        and movement.start_page <= page.printed_page <= movement.end_page
    ]
    return sorted(pages, key=lambda page: page.printed_page or 0)


def bundle_summary(bundle: RegisteredPrivateScoreBundle) -> dict[str, object]:
    score_pages = [page for page in bundle.pages if page.kind == "score"]
    return {
        "bundle_id": bundle.bundle_id,
        "work_title": bundle.work_title,
        "instrument": bundle.instrument,
        "tuning": bundle.tuning_name,
        "registered_pages": len(bundle.pages),
        "score_pages": len(score_pages),
        "movements": [movement.movement_id for movement in bundle.movements],
        "redistribution_allowed": bundle.redistribution_allowed,
    }


def summary_json(bundle: RegisteredPrivateScoreBundle) -> str:
    return json.dumps(bundle_summary(bundle), indent=2, sort_keys=True)
