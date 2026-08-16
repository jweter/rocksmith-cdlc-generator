from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator import shared_timeline


def _write_alignment(project: Path, *, source_path: Path, track_index: int = 1) -> None:
    alignment = AlignmentReport(
        source_path=str(source_path.resolve()),
        source_sha256="2" * 64,
        recording_sha256="1" * 64,
        track_index=track_index,
        audio_beat_start_index=4,
        global_offset_seconds=2.0,
        anchor_stride_beats=8,
        matched_beats=4,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=0.94,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=2.0,
                source_beat_index=0,
                audio_beat_index=4,
                confidence=0.95,
            ),
            AlignmentAnchor(
                source_time_seconds=1.5,
                audio_time_seconds=3.5,
                source_beat_index=3,
                audio_beat_index=7,
                confidence=0.93,
            ),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=1.5,
                audio_start_seconds=2.0,
                audio_end_seconds=3.5,
                rms_residual_seconds=0.01,
                max_abs_residual_seconds=0.02,
                confidence=0.94,
            )
        ],
    )
    path = project / "analysis" / "alignment.json"
    path.parent.mkdir(parents=True)
    alignment.write_json(path)


def _patch_authority(monkeypatch, project: Path) -> Path:
    bass_output = project / "sources" / "imported" / "score-bass.json"
    bass_output.parent.mkdir(parents=True)
    bass_output.write_text("bass", encoding="utf-8")

    bass_mapping = SimpleNamespace(
        role=ArrangementRole.bass,
        source_track_index=1,
        human_confirmed=True,
    )
    lead_mapping = SimpleNamespace(
        role=ArrangementRole.lead,
        source_track_index=2,
        human_confirmed=True,
    )
    score = SimpleNamespace(
        source_sha256="2" * 64,
        arrangement_mappings=[bass_mapping, lead_mapping],
        mapping_for=lambda role: bass_mapping if role is ArrangementRole.bass else lead_mapping,
    )
    fanout = SimpleNamespace(
        arrangements=[
            SimpleNamespace(
                role=ArrangementRole.bass,
                source_track_index=1,
                output_json="sources/imported/score-bass.json",
            )
        ]
    )

    monkeypatch.setattr(shared_timeline.ProjectManifest, "load", lambda _project: SimpleNamespace(source_sha256="1" * 64))
    monkeypatch.setattr(shared_timeline, "load_score_for_mapping_review", lambda _project: score)
    monkeypatch.setattr(shared_timeline, "_current_fanout", lambda _project, _score: fanout)
    return bass_output


def test_candidate_uses_same_authoritative_alignment_shape_as_promotion(monkeypatch, tmp_path: Path) -> None:
    bass_output = _patch_authority(monkeypatch, tmp_path)
    _write_alignment(tmp_path, source_path=bass_output)

    candidate = shared_timeline.build_shared_timeline_candidate(tmp_path)

    assert candidate.authority_role is ArrangementRole.bass
    assert candidate.authority_track_index == 1
    assert candidate.recording_sha256 == "1" * 64
    assert candidate.score_sha256 == "2" * 64
    assert candidate.confidence == pytest.approx(0.94)
    assert [anchor.audio_time_seconds for anchor in candidate.anchors] == [2.0, 3.5]


def test_candidate_rejects_stale_alignment_track_before_ui_can_enable(monkeypatch, tmp_path: Path) -> None:
    bass_output = _patch_authority(monkeypatch, tmp_path)
    _write_alignment(tmp_path, source_path=bass_output, track_index=2)

    with pytest.raises(ValueError, match="alignment track does not match"):
        shared_timeline.build_shared_timeline_candidate(tmp_path)


def test_candidate_rejects_alignment_from_non_authoritative_output(monkeypatch, tmp_path: Path) -> None:
    _patch_authority(monkeypatch, tmp_path)
    stale_output = tmp_path / "sources" / "imported" / "old-bass.json"
    stale_output.write_text("old", encoding="utf-8")
    _write_alignment(tmp_path, source_path=stale_output)

    with pytest.raises(ValueError, match="authoritative shared-score Bass output"):
        shared_timeline.build_shared_timeline_candidate(tmp_path)
