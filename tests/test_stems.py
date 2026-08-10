from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.stems import (
    AudioSeparatorBassStemSeparator,
    StemSeparationError,
)


def test_audio_separator_command_requests_bass_wav(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rocksmith_cdlc_generator.stems.shutil.which", lambda _: "/usr/bin/audio-separator")
    separator = AudioSeparatorBassStemSeparator(model="bass-model.onnx")

    command = separator.build_command(tmp_path / "song.wav", tmp_path / "out")

    assert command[0] == "/usr/bin/audio-separator"
    assert "--model_filename" in command
    assert command[command.index("--model_filename") + 1] == "bass-model.onnx"
    assert command[command.index("--single_stem") + 1] == "Bass"
    assert command[command.index("--sample_rate") + 1] == "44100"
    assert command[command.index("--output_format") + 1] == "WAV"


def test_audio_separator_directml_flag_is_opt_in(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rocksmith_cdlc_generator.stems.shutil.which", lambda _: "audio-separator")
    separator = AudioSeparatorBassStemSeparator(model="bass-model.onnx", use_directml=True)
    command = separator.build_command(tmp_path / "song.wav", tmp_path / "out")
    assert "--use_directml" in command


def test_missing_audio_separator_has_actionable_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("rocksmith_cdlc_generator.stems.shutil.which", lambda _: None)
    separator = AudioSeparatorBassStemSeparator(model="bass-model.onnx")
    with pytest.raises(StemSeparationError, match="not found on PATH"):
        separator.build_command(tmp_path / "song.wav", tmp_path / "out")
