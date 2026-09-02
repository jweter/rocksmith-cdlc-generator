from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .hashing import sha256_file
from .models import ProjectManifest
from .printed_notation_authoring import import_project_printed_notation_practice
from .printed_notation_import import PrintedNotationFixture
from .printed_notation_meter_validation import validate_printed_notation_meter
from .printed_score_project import (
    PrintedScoreProjectError,
    validate_printed_score_project_page,
)
from .score_measure_recognition import (
    PRIVATE_RECOGNITION_RELATIVE_PATH,
    PrintedScoreRecognitionCandidateSet,
    RecognitionProgress,
    recognize_score_measure_candidates,
)


class PrintedScoreDesktopActionError(RuntimeError):
    pass


_PAGE_PREFIX = re.compile(r"^page-(\d{3})-")
_PRACTICE_OUTPUT_DIRNAME = "printed_notation"
_PRACTICE_AUTHORITY_FILENAME = "printed-score-practice-authority.json"
_PRACTICE_XML_FILENAME = "arr_bass_RS2.xml"
_PRACTICE_CLICK_FILENAME = "click.wav"


def recognition_candidate_path(
    project_dir: Path,
    candidates: PrintedScoreRecognitionCandidateSet,
) -> Path:
    root = Path(project_dir).expanduser().resolve()
    return (
        root
        / PRIVATE_RECOGNITION_RELATIVE_PATH
        / f"page-{candidates.printed_page:03d}-{candidates.derivative_sha256[:12]}-candidates.json"
    )


def _validate_authorized_page(project_dir: Path, printed_page: int) -> None:
    try:
        validate_printed_score_project_page(project_dir, printed_page)
    except PrintedScoreProjectError as exc:
        raise PrintedScoreDesktopActionError(str(exc)) from exc


def _page_from_recognition_artifact(path: Path) -> int:
    match = _PAGE_PREFIX.match(path.name)
    if match is None:
        raise PrintedScoreDesktopActionError(
            f"printed-score recognition artifact does not encode its source page: {path.name}"
        )
    return int(match.group(1))


def recognize_printed_score_for_review(
    project_dir: Path,
    *,
    printed_page: int,
    model: str = "gemma3:4b",
    limit: int = 8,
    expected_system_count: int | None = None,
    progress: RecognitionProgress | None = None,
) -> tuple[PrintedScoreRecognitionCandidateSet, Path]:
    _validate_authorized_page(project_dir, printed_page)
    candidates = recognize_score_measure_candidates(
        project_dir,
        printed_page,
        model=model,
        limit=limit,
        expected_system_count=expected_system_count,
        progress=progress,
    )
    path = recognition_candidate_path(project_dir, candidates)
    if not path.is_file():
        raise PrintedScoreDesktopActionError(
            "recognition completed but its candidate JSON was not written where expected"
        )
    return candidates, path


def latest_reviewed_fixture(project_dir: Path) -> Path:
    root = Path(project_dir).expanduser().resolve()
    recognition_dir = root / PRIVATE_RECOGNITION_RELATIVE_PATH
    fixtures = sorted(
        recognition_dir.glob("*-reviewed-fixture.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not fixtures:
        raise PrintedScoreDesktopActionError(
            "no human-reviewed printed-score fixture exists yet; finish measure review first"
        )

    # A reviewed fixture is musical authority. Never select it solely by mtime: bind the
    # artifact back to the movement-authorized source page so stale or alternate-entry-
    # point candidates cannot cross a project's selected movement boundary.
    for fixture in fixtures:
        printed_page = _page_from_recognition_artifact(fixture)
        try:
            _validate_authorized_page(root, printed_page)
        except PrintedScoreDesktopActionError:
            continue
        return fixture

    raise PrintedScoreDesktopActionError(
        "reviewed printed-score fixtures exist, but none belong to the project's selected movement"
    )


def _practice_authority_path(project_dir: Path) -> Path:
    return project_dir / _PRACTICE_OUTPUT_DIRNAME / _PRACTICE_AUTHORITY_FILENAME


def _write_practice_build_authority(
    project_dir: Path,
    fixture_path: Path,
    outputs: dict[str, Path],
    *,
    count_in_measures: int,
    subdivision: str | None,
) -> Path:
    """Persist the exact human-review authority used for one practice build.

    Readiness must not be inferred from output existence alone. This receipt binds the
    current Rocksmith XML and click track to the SHA-256 of the human-reviewed fixture
    that authorized them. If review changes in place or a newer reviewed fixture becomes
    authoritative, the receipt no longer matches and the desktop returns to Build Practice.
    """

    root = project_dir.resolve()
    fixture = fixture_path.resolve()
    xml_path = outputs.get("xml")
    click_path = outputs.get("click_wav")
    if xml_path is None or not xml_path.is_file():
        raise PrintedScoreDesktopActionError("practice build did not produce Rocksmith XML")
    if click_path is None or not click_path.is_file():
        raise PrintedScoreDesktopActionError("practice build did not produce the click track")

    payload = {
        "schema_version": 1,
        "reviewed_fixture": fixture.relative_to(root).as_posix(),
        "reviewed_fixture_sha256": sha256_file(fixture),
        "xml_sha256": sha256_file(xml_path),
        "click_wav_sha256": sha256_file(click_path),
        "count_in_measures": count_in_measures,
        "subdivision": subdivision,
    }
    authority_path = _practice_authority_path(root)
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = authority_path.with_suffix(authority_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary_path, authority_path)
    return authority_path


def practice_build_is_current(project_dir: Path) -> bool:
    """Return whether practice outputs match the current human-reviewed authority."""

    root = Path(project_dir).expanduser().resolve()
    try:
        fixture = latest_reviewed_fixture(root)
    except (OSError, PrintedScoreDesktopActionError):
        return False

    output_dir = root / _PRACTICE_OUTPUT_DIRNAME
    xml_path = output_dir / _PRACTICE_XML_FILENAME
    click_path = output_dir / _PRACTICE_CLICK_FILENAME
    authority_path = _practice_authority_path(root)
    if not xml_path.is_file() or not click_path.is_file() or not authority_path.is_file():
        return False

    try:
        payload = json.loads(authority_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False

    try:
        fixture_relative_path = fixture.resolve().relative_to(root).as_posix()
        return (
            payload.get("reviewed_fixture") == fixture_relative_path
            and payload.get("reviewed_fixture_sha256") == sha256_file(fixture)
            and payload.get("xml_sha256") == sha256_file(xml_path)
            and payload.get("click_wav_sha256") == sha256_file(click_path)
        )
    except OSError:
        return False


def build_latest_reviewed_practice(
    project_dir: Path,
    *,
    count_in_measures: int = 2,
    subdivision: str | None = None,
) -> dict[str, Path]:
    if count_in_measures < 0:
        raise ValueError("count_in_measures must be >= 0")

    root = Path(project_dir).expanduser().resolve()
    manifest = ProjectManifest.load(root)
    fixture_path = latest_reviewed_fixture(root)
    fixture = PrintedNotationFixture.read_json(fixture_path)
    meter_report = validate_printed_notation_meter(fixture)
    if not meter_report.valid:
        first = meter_report.issues[0]
        raise PrintedScoreDesktopActionError(
            "reviewed printed score is not measure-complete: "
            f"measure {first.measure} {first.code}: {first.detail}. "
            "Return to Review and explicitly add the missing note/rest or correct the timing."
        )

    outputs = import_project_printed_notation_practice(
        root,
        fixture_path,
        title=manifest.title,
        artist=manifest.artist or "Practice",
        project_name=manifest.project_name,
        count_in_measures=count_in_measures,
        subdivision=subdivision,
    )
    outputs["practice_authority"] = _write_practice_build_authority(
        root,
        fixture_path,
        outputs,
        count_in_measures=count_in_measures,
        subdivision=subdivision,
    )
    return outputs
