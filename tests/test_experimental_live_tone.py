from __future__ import annotations

import importlib

import pytest

from rocksmith_cdlc_generator.audio_io import AudioDeviceInfo, AudioProbeRequest
from rocksmith_cdlc_generator.audition_dsp import ReferenceAuditionProcessor
from rocksmith_cdlc_generator.experimental_live_tone import (
    build_experimental_live_tone_preset,
    classify_input_level,
)
from rocksmith_cdlc_generator.sounddevice_backend import SoundDeviceBackend


class FakeRawStream:
    def __init__(self, owner, **kwargs) -> None:  # noqa: ANN001, ANN003
        self.owner = owner
        self.kwargs = kwargs
        self.latency = (0.005, 0.006)
        self.samplerate = kwargs["samplerate"]

    def __enter__(self):  # noqa: ANN204
        self.owner.last_stream = self
        frames = 128
        input_channels, output_channels = self.kwargs["channels"]
        indata = bytearray(frames * input_channels * 4)
        outdata = bytearray(frames * output_channels * 4)
        self.kwargs["callback"](indata, outdata, frames, None, None)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


class FakeSoundDevice:
    def __init__(self) -> None:
        self.last_stream: FakeRawStream | None = None

    def RawStream(self, **kwargs):  # noqa: ANN201, N802, ANN003
        return FakeRawStream(self, **kwargs)

    def sleep(self, milliseconds: int) -> None:
        return None


def _asio_device() -> AudioDeviceInfo:
    return AudioDeviceInfo(
        device_id=13,
        name="Focusrite USB ASIO",
        host_api="ASIO",
        max_input_channels=2,
        max_output_channels=2,
        default_sample_rate=48_000,
        default_low_input_latency=0.005,
        default_low_output_latency=0.005,
    )


def test_crunch_preset_changes_signal() -> None:
    processor = ReferenceAuditionProcessor()
    chain = build_experimental_live_tone_preset("crunch")

    source = [0.1, -0.2, 0.3]
    result = processor.process(source, chain)

    assert result != source
    assert len(result) == len(source)
    assert all(-1.0 <= sample <= 1.0 for sample in result)


def test_unknown_preset_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown experimental live tone preset"):
        build_experimental_live_tone_preset("mystery")


@pytest.mark.parametrize(
    ("peak", "expected"),
    [
        (0.50, "healthy"),
        (0.899, "healthy"),
        (0.90, "hot"),
        (0.989, "hot"),
        (0.99, "clipping_risk"),
        (0.999, "clipping_risk"),
        (1.0, "full_scale"),
        (-1.0, "full_scale"),
    ],
)
def test_input_level_classification(peak: float, expected: str) -> None:
    assert classify_input_level(peak) == expected


def test_processed_asio_monitor_still_requires_explicit_opt_in(monkeypatch) -> None:
    fake_sd = FakeSoundDevice()
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_sd)
    backend = SoundDeviceBackend(enable_asio=True)
    asio = _asio_device()

    with pytest.raises(RuntimeError, match="buffer size"):
        backend.run_processed_monitor_probe(
            asio,
            asio,
            AudioProbeRequest(),
            process_block=lambda samples: samples,
        )

    assert fake_sd.last_stream is None


def test_processed_asio_monitor_runs_only_with_explicit_opt_in(monkeypatch) -> None:
    fake_sd = FakeSoundDevice()
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_sd)
    backend = SoundDeviceBackend(
        enable_asio=True,
        allow_asio_buffer_negotiation=True,
    )
    asio = _asio_device()
    calls: list[int] = []

    metrics = backend.run_processed_monitor_probe(
        asio,
        asio,
        AudioProbeRequest(),
        process_block=lambda samples: calls.append(len(samples)) or samples,
    )

    assert calls == [128]
    assert fake_sd.last_stream is not None
    assert fake_sd.last_stream.kwargs["blocksize"] == 0
    assert metrics.callback_frames_min == 128
    assert metrics.callback_frames_max == 128
