from __future__ import annotations

import importlib

import pytest

from rocksmith_cdlc_generator.audio_io import AudioDeviceInfo, AudioProbeRequest
from rocksmith_cdlc_generator.sounddevice_backend import SoundDeviceBackend


class FakeWasapiSettings:
    def __init__(self, *, exclusive: bool = False) -> None:
        self.exclusive = exclusive


class FakeRawStream:
    def __init__(self, owner, **kwargs) -> None:  # noqa: ANN001, ANN003
        self.owner = owner
        self.kwargs = kwargs
        self.latency = (0.005, 0.006)
        self.samplerate = kwargs["samplerate"]

    def __enter__(self):  # noqa: ANN204
        self.owner.last_stream = self
        callback = self.kwargs["callback"]
        input_channels, output_channels = self.kwargs["channels"]
        frames = self.owner.callback_frames
        indata = bytearray(frames * input_channels * 4)
        outdata = bytearray(frames * output_channels * 4)
        callback(indata, outdata, frames, None, None)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


class FakeSoundDevice:
    WasapiSettings = FakeWasapiSettings

    def __init__(self, *, callback_frames: int = 128) -> None:
        self.input_checks: list[dict] = []
        self.output_checks: list[dict] = []
        self.last_stream: FakeRawStream | None = None
        self.callback_frames = callback_frames

    def check_input_settings(self, **kwargs) -> None:  # noqa: ANN003
        self.input_checks.append(kwargs)

    def check_output_settings(self, **kwargs) -> None:  # noqa: ANN003
        self.output_checks.append(kwargs)

    def RawStream(self, **kwargs):  # noqa: ANN201, N802, ANN003
        return FakeRawStream(self, **kwargs)

    def sleep(self, milliseconds: int) -> None:
        return None


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


def test_asio_probe_fails_closed_before_opening_stream(monkeypatch) -> None:
    fake_sd = FakeSoundDevice(callback_frames=144)
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_sd)
    backend = SoundDeviceBackend(enable_asio=True)
    asio = _device(
        13,
        "Focusrite USB ASIO",
        host_api="ASIO",
        inputs=2,
        outputs=2,
    )

    with pytest.raises(RuntimeError, match="buffer size"):
        backend.run_monitor_probe(asio, asio, AudioProbeRequest())

    assert fake_sd.last_stream is None


def test_asio_probe_requires_explicit_negotiation_opt_in(monkeypatch) -> None:
    fake_sd = FakeSoundDevice(callback_frames=144)
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_sd)
    backend = SoundDeviceBackend(
        enable_asio=True,
        allow_asio_buffer_negotiation=True,
    )
    asio = _device(
        13,
        "Focusrite USB ASIO",
        host_api="ASIO",
        inputs=2,
        outputs=2,
    )

    metrics = backend.run_monitor_probe(asio, asio, AudioProbeRequest(block_size=64))

    assert fake_sd.last_stream is not None
    assert fake_sd.last_stream.kwargs["blocksize"] == 0
    assert metrics.callback_frames_min == 144
    assert metrics.callback_frames_max == 144


def test_non_asio_probe_keeps_requested_callback_size(monkeypatch) -> None:
    fake_sd = FakeSoundDevice(callback_frames=128)
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_sd)
    backend = SoundDeviceBackend()
    input_device = _device(
        29,
        "Microphone (Scarlett 2i2 USB)",
        host_api="Windows WDM-KS",
        inputs=2,
        outputs=0,
    )
    output_device = _device(
        28,
        "Speakers (Scarlett 2i2 USB)",
        host_api="Windows WDM-KS",
        inputs=0,
        outputs=2,
    )

    backend.run_monitor_probe(input_device, output_device, AudioProbeRequest(block_size=64))

    assert fake_sd.last_stream is not None
    assert fake_sd.last_stream.kwargs["blocksize"] == 64
