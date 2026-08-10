from pathlib import Path

import pytest

from rocksmith_cdlc_generator import arrangement_gate
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.packaging_gate import PackagingBlockedError
from rocksmith_cdlc_generator.validation import ValidationReport


def _project(tmp_path: Path, arrangements: list[str]) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    ProjectManifest(
        project_name="gate-test",
        artist="Test Artist",
        title="Test Song",
        arrangement_instruments=arrangements,
        source_original_path="source.wav",
        source_project_path="source/source.wav",
        source_sha256="0" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=60.0,
            sample_rate_hz=44100,
            channels=2,
        ),
    ).save(project)
    return project


def _report(status: str) -> ValidationReport:
    return ValidationReport(
        status=status,
        can_package=status != "FAIL",
        fail_count=1 if status == "FAIL" else 0,
        warning_count=1 if status == "WARNING" else 0,
        review_queue=[],
    )


def test_gate_validates_only_configured_arrangements(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, ["lead", "rhythm"])
    calls: list[str] = []

    monkeypatch.setattr(
        arrangement_gate,
        "validate_project",
        lambda _: pytest.fail("Bass validator should not run for a guitar-only project"),
    )

    def fake_guitar(_, *, arrangement):
        calls.append(arrangement)
        return _report("PASS")

    monkeypatch.setattr(arrangement_gate, "validate_guitar_project", fake_guitar)

    gate = arrangement_gate.require_configured_arrangements_ready(project)

    assert calls == ["lead", "rhythm"]
    assert gate.status == "PASS"


def test_gate_blocks_when_any_configured_arrangement_fails(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, ["bass", "lead"])
    monkeypatch.setattr(arrangement_gate, "validate_project", lambda _: _report("PASS"))
    monkeypatch.setattr(arrangement_gate, "validate_guitar_project", lambda *_args, **_kwargs: _report("FAIL"))

    with pytest.raises(PackagingBlockedError, match="lead"):
        arrangement_gate.require_configured_arrangements_ready(project)


def test_gate_preserves_warning_status(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, ["bass", "lead"])
    monkeypatch.setattr(arrangement_gate, "validate_project", lambda _: _report("PASS"))
    monkeypatch.setattr(arrangement_gate, "validate_guitar_project", lambda *_args, **_kwargs: _report("WARNING"))

    gate = arrangement_gate.require_configured_arrangements_ready(project)

    assert gate.status == "WARNING"
