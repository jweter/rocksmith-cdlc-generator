from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.transcription import (
    BassTranscription,
    NoteEvent,
    write_transcription,
)
from rocksmith_cdlc_generator.unattended_audio_evidence_triage import (
    AudioEvidenceGap,
    classify_audio_evidence_gap,
)
from rocksmith_cdlc_generator.unattended_worker import (
    RecentProjectHealth,
    _diagnosis_payload,
    summarize_recent_recordings,
)


def _write_raw(
    project: Path,
    *,
    source: str = r"C:\\work\\audio\\normalized.wav",
    engine: str = "librosa-pyin",
    note_count: int = 8,
) -> None:
    raw = project / "analysis" / "bass_raw.json"
    write_transcription(
        BassTranscription(
            engine=engine,
            source_path=source,
            sample_rate_hz=44100,
            notes=[
                NoteEvent(
                    start=float(i),
                    duration=0.3,
                    midi=40 + i % 4,
                    confidence=0.1,
                    pitch_confidence=0.01,
                    timing_confidence=0.2,
                    review_required=True,
                )
                for i in range(note_count)
            ],
        ),
        raw,
    )


def _classify(project: Path, *, usable: int = 0, total: int | None = 8):
    return classify_audio_evidence_gap(
        project,
        qualification_status="insufficient_evidence",
        total_audio_notes=total,
        usable_audio_notes=usable,
    )


def test_full_mix_pyin_unqualified_explicitly_requests_independent_bass_separation(tmp_path):
    _write_raw(tmp_path)
    result = _classify(tmp_path)
    assert result.blocker_code == "FULL_MIX_PYIN_UNQUALIFIED"
    assert result.next_automation_dependency == "PRIVATE_BASS_STEM_SEPARATION"
    assert result.audio_input_class == "full_mix"
    assert not (tmp_path / "stems").exists()


def test_existing_bass_stem_routes_to_non_overwriting_independent_transcription(tmp_path):
    _write_raw(tmp_path)
    bass_stem = tmp_path / "stems" / "bass.wav"
    bass_stem.parent.mkdir()
    bass_stem.write_bytes(b"synthetic")
    result = _classify(tmp_path)
    assert result.blocker_code == "STEM_AVAILABLE_UNQUALIFIED_MIX"
    assert result.next_automation_dependency == "INDEPENDENT_STEM_TRANSCRIPTION"
    assert (tmp_path / "analysis" / "bass_raw.json").is_file()
    assert bass_stem.read_bytes() == b"synthetic"


def test_low_confidence_stem_requires_an_alternate_pitch_oracle(tmp_path):
    _write_raw(tmp_path, source=r"C:\\private\\stems\\bass.wav")
    result = _classify(tmp_path)
    assert result.blocker_code == "BASS_STEM_UNQUALIFIED"
    assert result.audio_input_class == "bass_stem"
    assert result.next_automation_dependency == "ALTERNATE_PITCH_ORACLE"


def test_missing_evidence_has_distinct_machine_action(tmp_path):
    result = _classify(tmp_path, total=None)
    assert result.blocker_code == "BASS_TRANSCRIPTION_MISSING"
    assert result.next_automation_dependency == "BASS_AUDIO_TRANSCRIPTION"


def test_corrupted_evidence_never_becomes_a_song_pass(tmp_path):
    raw = tmp_path / "analysis" / "bass_raw.json"
    raw.parent.mkdir()
    raw.write_text("{malformed", encoding="utf-8")
    result = _classify(tmp_path)
    assert result.blocker_code == "BASS_TRANSCRIPTION_UNREADABLE"
    assert result.next_automation_dependency == "VALIDATE_EXISTING_TRANSCRIPTION"


def test_zero_note_transcription_needs_an_independent_pitch_oracle(tmp_path):
    _write_raw(tmp_path, note_count=0)
    result = _classify(tmp_path, total=0)
    assert result.blocker_code == "NO_BASS_NOTES"
    assert result.next_automation_dependency == "ALTERNATE_PITCH_ORACLE"


def test_unknown_audio_input_is_not_falsely_classed_as_a_clean_bass_stem(tmp_path):
    _write_raw(tmp_path, source=r"C:\\private\\capture.wav", engine="external")
    result = _classify(tmp_path)
    assert result.blocker_code == "UNQUALIFIED_UNKNOWN_SOURCE"
    assert result.audio_input_class == "other"


def test_supported_audio_but_ambiguous_timing_needs_independent_oracle(tmp_path):
    _write_raw(tmp_path)
    result = _classify(tmp_path, usable=5)
    assert result.blocker_code == "AMBIGUOUS_ALIGNMENT"
    assert result.next_automation_dependency == "INDEPENDENT_TIMING_ORACLE"


def test_qualification_pass_and_fail_are_not_overwritten_by_heuristic(tmp_path):
    for status in ("pass", "review_required"):
        gap = classify_audio_evidence_gap(
            tmp_path,
            qualification_status=status,
            total_audio_notes=8,
            usable_audio_notes=0,
        )
        assert gap.blocker_code == "NONE"
        assert gap.next_automation_dependency == "NONE"


def _health(fingerprint: str, *, gap: AudioEvidenceGap | None):
    return RecentProjectHealth(
        project_name="private project title must not leak to sanitized summaries",
        recording_sha256=fingerprint,
        status="REVIEW_REQUIRED",
        qualification_status="insufficient_evidence",
        best_shift_seconds=0.0,
        compared_symbolic_notes=64,
        usable_audio_notes=0,
        total_audio_notes=392,
        confidence_qualified_audio_notes=0,
        timing_qualified_audio_notes=0,
        pitch_qualified_audio_notes=0,
        reason="private absolute path must not leak",
        audio_evidence_gap=gap,
    )


def test_shared_recording_is_counted_once_but_all_project_score_views_are_retained():
    gap = AudioEvidenceGap(
        blocker_code="FULL_MIX_PYIN_UNQUALIFIED",
        next_automation_dependency="PRIVATE_BASS_STEM_SEPARATION",
        audio_input_class="full_mix",
    )
    items = [
        _health("a" * 64, gap=gap),
        _health("a" * 64, gap=gap),
        _health("a" * 64, gap=gap),
        _health("b" * 64, gap=gap),
        _health("c" * 64, gap=gap),
        _health("d" * 64, gap=gap),
    ]
    coverage = summarize_recent_recordings(items)
    assert coverage.project_views == 6
    assert coverage.unique_recordings == 4
    assert coverage.duplicate_project_views == 2
    assert coverage.full_mix_unqualified_views == 6
    assert len(items) == 6


def test_empty_recent_health_summary_is_zero_not_an_invented_pass():
    coverage = summarize_recent_recordings([])
    assert coverage.project_views == 0
    assert coverage.unique_recordings == 0
    assert coverage.duplicate_project_views == 0


def test_private_ollama_advice_is_allowlisted_with_only_codes_and_numbers():
    gap = AudioEvidenceGap(
        blocker_code="FULL_MIX_PYIN_UNQUALIFIED",
        next_automation_dependency="PRIVATE_BASS_STEM_SEPARATION",
        audio_input_class="full_mix",
    )
    payload = _diagnosis_payload(
        scenario_results=[],
        recent_health=[_health("a" * 64, gap=gap)],
    )
    item = payload["recent_project_health"][0]
    assert item["audio_blocker_code"] == "FULL_MIX_PYIN_UNQUALIFIED"
    assert item["next_automation_dependency"] == "PRIVATE_BASS_STEM_SEPARATION"
    assert "project_name" not in item
    assert "recording_sha256" not in item
    assert "private" not in str(payload).lower()
