from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


class AudioOutputUnavailable(RuntimeError):
    """Raised when the optional desktop audio runtime cannot provide output devices."""


@dataclass(frozen=True)
class AudioOutputDevice:
    index: int
    name: str
    max_output_channels: int
    default_samplerate: float
    is_default: bool = False

    @property
    def label(self) -> str:
        suffix = " · default" if self.is_default else ""
        return f"{self.index}: {self.name} ({self.max_output_channels} ch){suffix}"


def _settings_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".rocksmith-cdlc-generator"))
    return base / "RocksmithCDLCGenerator" / "audio-output.json"


def _sounddevice():
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - depends on optional packaged runtime.
        raise AudioOutputUnavailable(
            "Audio device diagnostics are unavailable because the sounddevice runtime could not be loaded."
        ) from exc
    return sd


def _default_output_index(sd: Any) -> int | None:
    try:
        value = sd.default.device
        if isinstance(value, (tuple, list)):
            return int(value[1]) if int(value[1]) >= 0 else None
        # sounddevice's _InputOutputPair supports indexing without being tuple/list.
        output = int(value[1])
        return output if output >= 0 else None
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


def list_output_devices() -> list[AudioOutputDevice]:
    """Return output-capable sounddevice endpoints without changing global audio state."""

    sd = _sounddevice()
    try:
        raw_devices = sd.query_devices()
    except Exception as exc:
        raise AudioOutputUnavailable(f"Could not query Windows audio output devices: {exc}") from exc

    default_output = _default_output_index(sd)
    devices: list[AudioOutputDevice] = []
    for index, raw in enumerate(raw_devices):
        try:
            channels = int(raw["max_output_channels"])
        except (KeyError, TypeError, ValueError):
            continue
        if channels <= 0:
            continue
        name = str(raw.get("name", f"Output {index}"))
        try:
            samplerate = float(raw.get("default_samplerate", 0.0))
        except (TypeError, ValueError):
            samplerate = 0.0
        devices.append(
            AudioOutputDevice(
                index=index,
                name=name,
                max_output_channels=channels,
                default_samplerate=samplerate,
                is_default=index == default_output,
            )
        )
    return devices


def load_output_preference() -> tuple[int | None, str | None]:
    path = _settings_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    raw_index = payload.get("device_index")
    raw_name = payload.get("device_name")
    try:
        index = int(raw_index) if raw_index is not None else None
    except (TypeError, ValueError):
        index = None
    name = str(raw_name) if isinstance(raw_name, str) and raw_name.strip() else None
    return index, name


def preferred_output_device(devices: list[AudioOutputDevice]) -> AudioOutputDevice | None:
    """Resolve a persisted endpoint conservatively, then fall back to Windows default."""

    saved_index, saved_name = load_output_preference()
    if saved_name is not None:
        exact = next(
            (
                device
                for device in devices
                if device.name == saved_name and (saved_index is None or device.index == saved_index)
            ),
            None,
        )
        if exact is not None:
            return exact
        by_name = next((device for device in devices if device.name == saved_name), None)
        if by_name is not None:
            return by_name
    return next((device for device in devices if device.is_default), devices[0] if devices else None)


def select_output_device(device: AudioOutputDevice, *, persist: bool = True) -> None:
    """Select one application-wide sounddevice output and optionally persist metadata."""

    sd = _sounddevice()
    try:
        current = sd.default.device
        input_index = int(current[0])
        sd.default.device = (input_index, device.index)
    except Exception as exc:
        raise AudioOutputUnavailable(f"Could not select audio output '{device.name}': {exc}") from exc

    if not persist:
        return
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"device_index": device.index, "device_name": device.name},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def describe_output_devices(devices: list[AudioOutputDevice]) -> str:
    if not devices:
        return "No output-capable audio devices were reported by the sounddevice runtime."
    lines = ["Available audio outputs:"]
    for device in devices:
        rate = f"{device.default_samplerate / 1000:.1f} kHz" if device.default_samplerate > 0 else "rate unknown"
        marker = " [Windows/default]" if device.is_default else ""
        lines.append(
            f"- {device.index}: {device.name} · {device.max_output_channels} output channel(s) · {rate}{marker}"
        )
    return "\n".join(lines)
