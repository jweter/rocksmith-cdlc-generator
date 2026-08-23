from pathlib import Path

import pytest

from rocksmith_cdlc_generator import arrangement_gate
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.packaging_gate import PackagingBlockedError
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
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


def _register_confirmed_lead_mapping(project: Path) -> None:
    """Mirrors what ``cdlc-score-map confirm lead <index>`` persists -- deliberately
    without touching ``project.json``'s ``arrangement_instruments``, since neither
    that CLI command nor ``score_mapping_review.confirm_score_mapping`` update it.
    """

    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"complete-score")
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=sha256_file(stored),
        source_format="gp5",
        imported_relative_path=str(stored.relative_to(project)),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead Guitar", note_count=100),
            ScoreTrackCandidate(source_track_index=1, name="Bass", note_count=90),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.0,
                basis=["human selected score track explicitly"],
                human_confirmed=True,
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")


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


def test_configured_arrangement_roles_includes_undeclared_human_confirmed_role(tmp_path: Path) -> None:
    """#304/#193: a bass-only CLI project (``cdlc new --instrument bass``) whose Lead
    mapping is later human-confirmed (``cdlc-score-map confirm lead``) never updates
    ``arrangement_instruments`` -- but ``multi_arrangement_plan._confirmed_guitar_roles``
    already treats that confirmation alone as real Lead project work, generating a real
    ``lead_validation_report.json`` and Rocksmith XML export. Pre-fix,
    ``configured_arrangement_roles`` read only ``arrangement_instruments``, so this real
    Lead arrangement was silently excluded from both the pre-package validation gate
    (``require_configured_arrangements_ready``) and ``prepare_dlcbuilder_project``'s
    build loop -- a FAIL Lead report could not block packaging, and a PASSing one could
    not be included in the shipped DLC.
    """

    project = _project(tmp_path, ["bass"])
    _register_confirmed_lead_mapping(project)

    roles = arrangement_gate.configured_arrangement_roles(project)

    assert roles == ["bass", "lead"]


def test_gate_blocks_on_undeclared_human_confirmed_role_failure(tmp_path: Path, monkeypatch) -> None:
    """The undeclared-but-confirmed Lead role must still gate packaging when its
    validation is FAIL -- exactly the protection a manifest-declared role already gets.
    Pre-fix, this Lead role was invisible to ``configured_arrangement_roles`` entirely,
    so its FAIL status could never block ``require_configured_arrangements_ready``.
    """

    project = _project(tmp_path, ["bass"])
    _register_confirmed_lead_mapping(project)
    monkeypatch.setattr(arrangement_gate, "validate_project", lambda _: _report("PASS"))
    monkeypatch.setattr(arrangement_gate, "validate_guitar_project", lambda *_args, **_kwargs: _report("FAIL"))

    with pytest.raises(PackagingBlockedError, match="lead"):
        arrangement_gate.require_configured_arrangements_ready(project)


def test_configured_arrangement_roles_ignores_unconfirmed_mapping(tmp_path: Path) -> None:
    """A score mapping that exists but was never human-confirmed must not silently
    expand the configured role set -- only an explicit human confirmation (the same
    signal ``multi_arrangement_plan._confirmed_guitar_roles`` requires) does."""

    project = _project(tmp_path, ["bass"])
    _register_confirmed_lead_mapping(project)
    contract = project / "sources" / "score" / "source.json"
    score = ProjectScoreSource.read_json(contract)
    unconfirmed_mapping = score.arrangement_mappings[0].model_copy(update={"human_confirmed": False})
    score = score.model_copy(update={"arrangement_mappings": [unconfirmed_mapping]})
    score.write_json(contract)

    roles = arrangement_gate.configured_arrangement_roles(project)

    assert roles == ["bass"]
