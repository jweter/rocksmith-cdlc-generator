from __future__ import annotations

from array import array
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.audio_playback import PlaybackUnavailable, ProjectAudioTransport


def _pcm(path: Path, *, frames: int = 6000, sample_rate: int = 12000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(array("h", [100] * frames).tobytes())


def test_aligned_preview_switch_preserves_same_song_clock(tmp_path: Path, monkeypatch) -> None:
    original = tmp_path / "audio" / "normalized.wav"
    alternate = tmp_path / "audio" / "derived" / "instrument_focus" / "demo.wav"
    _pcm(original)
    _pcm(alternate)
    monkeypatch.setattr("rocksmith_cdlc_generator.audio_playback.normalized_audio_path", lambda _: original)
    transport = ProjectAudioTransport(tmp_path)
    try:
        transport.seek(0.25)
        transport.set_loop(0.2, 0.4)
        original_clock = transport.position_seconds
        transport.set_preview_source(alternate)
        assert transport.position_seconds == original_clock
        assert transport.preview_source_path == alternate
        assert transport.original_audio_path == original
        assert transport.loop_range == pytest.approx((0.2, 0.4))
        transport.set_preview_source(None)
        assert transport.preview_source_path == original
        assert transport.position_seconds == original_clock
    finally:
        transport.close()


def test_preview_rejects_misaligned_and_external_audio(tmp_path: Path, monkeypatch) -> None:
    original = tmp_path / "audio" / "normalized.wav"
    _pcm(original)
    monkeypatch.setattr("rocksmith_cdlc_generator.audio_playback.normalized_audio_path", lambda _: original)
    wrong = tmp_path / "stems" / "bass.wav"
    _pcm(wrong, frames=5999)
    outside = tmp_path.parent / "outside.wav"
    _pcm(outside)
    transport = ProjectAudioTransport(tmp_path)
    try:
        with pytest.raises(PlaybackUnavailable, match="do not match"):
            transport.set_preview_source(wrong)
        with pytest.raises(PlaybackUnavailable, match="inside the local project"):
            transport.set_preview_source(outside)
        assert transport.preview_source_path == tmp_path / "audio" / "normalized.wav"
    finally:
        transport.close()
