from __future__ import annotations

from pathlib import Path

from .models import ProjectManifest
from .printed_notation_authoring import import_project_printed_notation_practice
from .printed_notation_import import PrintedNotationFixture
from .printed_notation_meter_validation import validate_printed_notation_meter
from .printed_score_project import (
    PrintedScoreProjectError,
    read_printed_score_project_authority,
)
from .score_measure_recognition import (
    PRIVATE_RECOGNITION_RELATIVE_PATH,
    PrintedScoreRecognitionCandidateSet,
    recognize_score_measure_candidates,
)


class PrintedScoreDesktopActionError(RuntimeError):
    pass


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
        authority = read_printed_score_project_authority(project_dir)
    except PrintedScoreProjectError as exc:
        raise PrintedScoreDesktopActionError(str(exc)) from exc
    start_page = int(authority["start_page"])
    end_page = int(authority["end_page"])
    if not start_page <= printed_page <= end_page:
        raise PrintedScoreDesktopActionError(
            f"printed page {printed_page} is outside selected movement "
            f"{authority['movement_id']!r} (pages {start_page}-{end_page})"
        )


def recognize_printed_score_for_review(
    project_dir: Path,
    *,
    printed_page: int,
    model: str = "gemma3:4b",
    limit: int = 8,
    expected_system_count: int | None = None,
) -> tuple[PrintedScoreRecognitionCandidateSet, Path]:
    _validate_authorized_page(project_dir, printed_page)
    candidates = recognize_score_measure_candidates(
        project_dir,
        printed_page,
        model=model,
        limit=limit,
        expected_system_count=expected_system_count,
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
    return fixtures[0]


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

    return import_project_printed_notation_practice(
        root,
        fixture_path,
        title=manifest.title,
        artist=manifest.artist or "Practice",
        project_name=manifest.project_name,
        count_in_measures=count_in_measures,
        subdivision=subdivision,
    )
