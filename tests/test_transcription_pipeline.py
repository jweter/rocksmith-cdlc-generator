from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.transcription_pipeline import _select_bass_input


def test_explicit_bass_input_has_highest_priority(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "stems").mkdir(parents=True)
    stem = project / "stems" / "bass.wav"
    stem.write_bytes(b"stem")
    explicit = tmp_path / "explicit.wav"
    explicit.write_bytes(b"explicit")

    assert _select_bass_input(project, explicit) == explicit.resolve()


def test_generated_bass_stem_is_preferred_over_full_mix(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "stems").mkdir(parents=True)
    (project / "audio").mkdir(parents=True)
    stem = project / "stems" / "bass.wav"
    stem.write_bytes(b"stem")
    (project / "audio" / "normalized.wav").write_bytes(b"mix")

    assert _select_bass_input(project, None) == stem


def test_full_mix_is_fallback_when_no_stem_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    expected = project / "audio" / "normalized.wav"
    assert _select_bass_input(project, None) == expected
