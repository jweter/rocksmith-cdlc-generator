from __future__ import annotations

from pathlib import Path

from .transcription_pipeline import analyze_project_bass


def ensure_bass_timing_evidence(project_dir: Path) -> bool:
    """Create missing audio-derived Bass evidence for unattended timing qualification.

    Returns True only when this call created ``analysis/bass_raw.json``. Existing evidence
    is never overwritten. The caller remains responsible for rerunning qualification and
    treating any transcription/qualification failure as fail-closed worker evidence.
    """

    project = project_dir.expanduser().resolve()
    evidence = project / "analysis" / "bass_raw.json"
    if evidence.is_file():
        return False

    normalized_audio = project / "audio" / "normalized.wav"
    if not normalized_audio.is_file():
        return False

    analyze_project_bass(project, engine="librosa-pyin", input_path=normalized_audio)
    if not evidence.is_file():
        raise RuntimeError("Bass transcription completed without producing analysis/bass_raw.json")
    return True
