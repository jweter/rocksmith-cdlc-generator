from __future__ import annotations

import importlib

import pytest

from rocksmith_cdlc_generator.audio_io import AudioDeviceInfo, AudioProbeRequest
from rocksmith_cdlc_generator.sounddevice_backend import SoundDeviceBackend


class FakeWasapiSettings:
    def __init__(self, *, exclusive: bool = False) -> None:
        self.exclusive = exclusive


class FakeSoundDevice:
    WasapiSettings = FakeWasapiSettings

    def __init__(self) -> None:
        self.input_checks: list[dict] = []
        self.output_checks: list[dict] = []

    def check_input_settings(self, **kwargs) -> None:  # noqa: ANN003
        self.input_checks.append(kwargs)

    def check_output_settings(self, **kwargs) -> None:  # noqa: ANN003
        self.output_checks.append(kwargs)


def _device(device_id: int, name: str, *, host_api: str, inputs: int, outputs: int) -> AudioDeviceInfo:
    return AudioDeviceInfo(
        device_id=device_id,
        name=name,
        host_api=host_api,
        max_input_channels=inputs,
        max_output_channels=outputs,
        default_sample_rate=48_000,
        default_low_input_latency=0.005,
        default_low_output_latency=0.005,
    )


def test_wasapi_exclusive_settings_are_applied_to_validation(monkeypatch) -> None:
    fake_sd = FakeSoundDevice()
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_sd)
    backend = SoundDeviceBackend(wasapi_exclusive=True)
    input_device = _device(
        15,
        "Microphone (Scarlett 2i2 USB)",
        host_api="Windows WASAPI",
        inputs=2,
        outputs=0,
    )
    output_device = _device(
        12,
        "Speakers (Scarlett 2i2 USB)",
        host_api="Windows WASAPI",
        inputs=0,
        outputs=2,
    )

    backend.validate_settings(input_device, output_device, AudioProbeRequest(input_channel=1))

    input_extra = fake_sd.input_checks[0]["extra_settings"]
    output_extra = fake_sd.output_checks[0]["extra_settings"]
    assert isinstance(input_extra, FakeWasapiSettings)
    assert isinstance(output_extra, FakeWasapiSettings)
    assert input_extra.exclusive is True
    assert output_extra.exclusive is True


def test_wasapi_exclusive_rejects_non_wasapi_fallback(monkeypatch) -> None:
    fake_sd = FakeSoundDevice()
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_sd)
    backend = SoundDeviceBackend(wasapi_exclusive=True)
    input_device = _device(
        1,
        "Microphone (Scarlett 2i2 USB)",
        host_api="MME",
        inputs=2,
        outputs=0,
    )
    output_device = _device(
        5,
        "Speakers (Scarlett 2i2 USB)",
        host_api="MME",
        inputs=0,
        outputs=2,
    )

    with pytest.raises(RuntimeError, match="WASAPI exclusive mode requires"):
        backend.validate_settings(input_device, output_device, AudioProbeRequest())
