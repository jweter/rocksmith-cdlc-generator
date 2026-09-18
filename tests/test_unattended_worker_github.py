from __future__ import annotations

from pathlib import Path
import subprocess

from rocksmith_cdlc_generator.unattended_worker import (
    LocalDiagnosis,
    RecentProjectHealth,
    UnattendedWorkerReport,
    WorkerScenarioResult,
)
from rocksmith_cdlc_generator.unattended_worker_github import publish_sanitized_status


def _report() -> UnattendedWorkerReport:
    return UnattendedWorkerReport(
        started_at_utc="2026-09-16T12:00:00+00:00",
        completed_at_utc="2026-09-16T12:01:00+00:00",
        hostname="PRIVATE-HOST",
        build_version="0.1.0",
        build_commit_sha="a" * 40,
        status="FAIL",
        scenario_results=[
            WorkerScenarioResult(
                scenario_id="private-metallica-scenario",
                status="FAIL",
                evidence_path="C:/private/song/evidence.json",
                checks=[
                    {
                        "code": "first_playable_time",
                        "status": "FAIL",
                        "observed": 11.77,
                        "expected": 7.13,
                    }
                ],
            )
        ],
        recent_project_health=[
            RecentProjectHealth(
                project_name="Private Song Title",
                recording_sha256="b" * 64,
                status="FAIL",
                qualification_status="review_required",
                best_shift_seconds=-4.64,
                first_projected_note_seconds=11.77,
                first_audio_note_seconds=7.13,
                reason="private diagnosis text",
            )
        ],
        diagnosis=LocalDiagnosis(
            category="timing_phase",
            summary="derived summary",
            likely_root_cause="derived cause",
            next_automated_action="rerun deterministic phase regression",
            human_required=False,
            confidence=0.95,
        ),
    )


def test_publication_is_noop_off_windows(tmp_path: Path) -> None:
    assert publish_sanitized_status(_report(), tmp_path, os_name="posix") == "LOCAL_ONLY_NON_WINDOWS"
    assert not (tmp_path / "github-publication.json").exists()


def test_publication_posts_only_sanitized_aggregate_status(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    status = publish_sanitized_status(
        _report(),
        tmp_path,
        os_name="nt",
        which=lambda _name: "gh.exe",
        runner=runner,
    )

    assert status == "PUBLISHED"
    assert len(calls) == 2
    body = calls[1][calls[1].index("--body") + 1]
    assert "4.640s" in body
    assert "FAIL 1" in body
    assert "Private Song Title" not in body
    assert "private-metallica-scenario" not in body
    assert "C:/private" not in body
    assert "PRIVATE-HOST" not in body
    assert "recording_sha256" not in body
    assert "bbbbbbbb" not in body
    assert "private diagnosis text" not in body


def test_publication_aggregates_allow_listed_review_reasons_without_private_text(tmp_path: Path) -> None:
    report = _report().model_copy(
        update={
            "status": "REVIEW_REQUIRED",
            "scenario_results": [],
            "recent_project_health": [
                RecentProjectHealth(
                    project_name="Secret One",
                    recording_sha256="c" * 64,
                    status="REVIEW_REQUIRED",
                    qualification_status="insufficient_evidence",
                    best_shift_seconds=0.0,
                    reason="Fewer than four strong symbolic/audio events were available at C:/private/one.",
                ),
                RecentProjectHealth(
                    project_name="Secret Two",
                    recording_sha256="d" * 64,
                    status="REVIEW_REQUIRED",
                    qualification_status="insufficient_evidence",
                    best_shift_seconds=0.0,
                    reason="No audio-derived Bass transcription exists for C:/private/two.",
                ),
            ],
            "diagnosis": None,
        }
    )
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    assert (
        publish_sanitized_status(
            report,
            tmp_path,
            os_name="nt",
            which=lambda _name: "gh.exe",
            runner=runner,
        )
        == "PUBLISHED"
    )
    body = calls[1][calls[1].index("--body") + 1]
    assert "insufficient_strong_events 1" in body
    assert "missing_audio_bass_transcription 1" in body
    assert "Secret One" not in body
    assert "Secret Two" not in body
    assert "C:/private" not in body
    assert "Fewer than" not in body


def test_publication_deduplicates_unchanged_aggregate_state(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    first = publish_sanitized_status(
        _report(),
        tmp_path,
        os_name="nt",
        which=lambda _name: "gh.exe",
        runner=runner,
    )
    calls.clear()
    second = publish_sanitized_status(
        _report(),
        tmp_path,
        os_name="nt",
        which=lambda _name: "gh.exe",
        runner=runner,
    )

    assert first == "PUBLISHED"
    assert second == "UNCHANGED"
    assert calls == []


def test_publication_failure_never_changes_product_reality_status(tmp_path: Path) -> None:
    report = _report()

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if command[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="network unavailable")

    status = publish_sanitized_status(
        report,
        tmp_path,
        os_name="nt",
        which=lambda _name: "gh.exe",
        runner=runner,
    )

    assert status == "LOCAL_ONLY"
    assert report.status == "FAIL"
