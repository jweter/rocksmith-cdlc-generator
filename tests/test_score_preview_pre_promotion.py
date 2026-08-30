from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion
from rocksmith_cdlc_generator.score_preview import _alignment_from_candidate, _preview_alignment_for_role
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline


def _candidate() -> SharedTimeline:
    return SharedTimeline(
        recording_sha256="1" * 64,
        score_sha256="2" * 64,
        authority_role=ArrangementRole.bass,
        authority_track_index=2,
        authority_output_json="sources/imported/bass.json",
        authority_output_sha256="3" * 64,
        inherited_roles=[ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm],
        audio_beat_start_index=4,
        global_offset_seconds=7.109,
        anchor_stride_beats=8,
        matched_beats=16,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.008,
        max_abs_residual_seconds=0.03,
        confidence=0.96,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=7.109,
                source_beat_index=0,
                audio_beat_index=4,
                confidence=0.97,
            ),
            AlignmentAnchor(
                source_time_seconds=8.0,
                audio_time_seconds=15.109,
                source_beat_index=16,
                audio_beat_index=20,
                confidence=0.95,
            ),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=8.0,
                audio_start_seconds=7.109,
                audio_end_seconds=15.109,
                rms_residual_seconds=0.01,
                max_abs_residual_seconds=0.03,
                confidence=0.96,
            )
        ],
        warnings=["fixture warning"],
    )


def test_candidate_materialization_keeps_shared_transform_but_role_specific_source() -> None:
    candidate = _candidate()
    output = Path("C:/project/sources/imported/lead.json")

    report = _alignment_from_candidate(
        candidate,
        ArrangementRole.lead,
        output=output,
        source_track_index=1,
    )

    assert report.source_path == str(output)
    assert report.track_index == 1
    assert report.source_sha256 == candidate.score_sha256
    assert report.recording_sha256 == candidate.recording_sha256
    assert report.global_offset_seconds == candidate.global_offset_seconds
    assert report.anchors == candidate.anchors
    assert report.regions == candidate.regions
    assert report.warnings == candidate.warnings


def test_preview_uses_exact_candidate_when_shared_timeline_has_not_been_promoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    candidate = _candidate()
    calls = {"candidate": 0}

    def _no_promoted_timeline(_project: Path, _role: ArrangementRole):
        raise FileNotFoundError(project / "analysis" / "shared_timeline.json")

    def _build_candidate(_project: Path) -> SharedTimeline:
        calls["candidate"] += 1
        return candidate

    monkeypatch.setattr("rocksmith_cdlc_generator.score_preview.alignment_for_role", _no_promoted_timeline)
    monkeypatch.setattr("rocksmith_cdlc_generator.score_preview.build_shared_timeline_candidate", _build_candidate)

    output = project / "sources" / "imported" / "bass.json"
    report = _preview_alignment_for_role(
        project,
        ArrangementRole.bass,
        output=output,
        source_track_index=2,
    )

    assert calls["candidate"] == 1
    assert report.source_path == str(output)
    assert report.track_index == 2
    assert report.global_offset_seconds == pytest.approx(7.109)
    assert not (project / "analysis" / "shared_timeline.json").exists()


def test_preview_keeps_promoted_timeline_authoritative_when_it_exists_but_is_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "song"
    shared_path = project / "analysis" / "shared_timeline.json"
    shared_path.parent.mkdir(parents=True)
    shared_path.write_text("stale promoted authority", encoding="utf-8")

    def _broken_promoted_timeline(_project: Path, _role: ArrangementRole):
        raise FileNotFoundError(project / "sources" / "imported" / "missing.json")

    def _must_not_fallback(_project: Path) -> SharedTimeline:  # pragma: no cover - assertion boundary
        raise AssertionError("stale promoted authority must not fall back to an unpromoted candidate")

    monkeypatch.setattr("rocksmith_cdlc_generator.score_preview.alignment_for_role", _broken_promoted_timeline)
    monkeypatch.setattr("rocksmith_cdlc_generator.score_preview.build_shared_timeline_candidate", _must_not_fallback)

    with pytest.raises(FileNotFoundError, match="missing.json"):
        _preview_alignment_for_role(
            project,
            ArrangementRole.bass,
            output=project / "sources" / "imported" / "bass.json",
            source_track_index=2,
        )


def test_preview_uses_promoted_alignment_without_building_a_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    promoted = _alignment_from_candidate(
        _candidate(),
        ArrangementRole.rhythm,
        output=project / "sources" / "imported" / "rhythm.json",
        source_track_index=0,
    )

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_preview.alignment_for_role",
        lambda _project, _role: promoted,
    )

    def _must_not_build(_project: Path) -> SharedTimeline:  # pragma: no cover - assertion boundary
        raise AssertionError("candidate builder must not run when promoted alignment resolves")

    monkeypatch.setattr("rocksmith_cdlc_generator.score_preview.build_shared_timeline_candidate", _must_not_build)

    result = _preview_alignment_for_role(
        project,
        ArrangementRole.rhythm,
        output=project / "sources" / "imported" / "rhythm.json",
        source_track_index=0,
    )
    assert result is promoted
