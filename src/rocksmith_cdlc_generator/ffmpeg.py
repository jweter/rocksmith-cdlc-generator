from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .models import AudioMetadata


class FFmpegUnavailable(RuntimeError):
    pass


def _require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise FFmpegUnavailable(
            f"{name} was not found on PATH. Install FFmpeg and ensure both ffmpeg and ffprobe are available."
        )
    return executable


def inspect_audio(path: Path) -> AudioMetadata:
    ffprobe = _require_tool("ffprobe")
    command = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration,format_name:stream=codec_type,codec_name,sample_rate,channels",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    audio_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise ValueError(f"No audio stream found in {path}")
    fmt = payload.get("format", {})
    return AudioMetadata(
        duration_seconds=float(fmt["duration"]),
        sample_rate_hz=int(audio_stream["sample_rate"]),
        channels=int(audio_stream["channels"]),
        codec_name=audio_stream.get("codec_name"),
        format_name=fmt.get("format_name"),
    )


def normalize_audio(source: Path, destination: Path) -> list[str]:
    ffmpeg = _require_tool("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", str(source),
        "-vn",
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        str(destination),
    ]
    subprocess.run(command, check=True)
    return command


def create_preview_audio(
    source: Path,
    destination: Path,
    *,
    start_seconds: float,
    duration_seconds: float = 30.0,
) -> list[str]:
    """Create a deterministic 44.1 kHz PCM preview for DLC Builder."""
    if start_seconds < 0:
        raise ValueError("Preview start must be non-negative")
    if duration_seconds <= 0:
        raise ValueError("Preview duration must be positive")

    ffmpeg = _require_tool("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-ss", f"{start_seconds:.3f}",
        "-i", str(source),
        "-t", f"{duration_seconds:.3f}",
        "-vn",
        "-ar", "44100",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        str(destination),
    ]
    subprocess.run(command, check=True)
    return command
