from __future__ import annotations

from rocksmith_cdlc_generator.audio_io import (
    AudioDeviceInfo,
    AudioProbeRequest,
    AudioStreamMetrics,
    qualify_scarlett_2i2,
    resolve_scarlett_2i2_devices,
)


def _device(
    device_id: int,
    name: str,
    *,
    host_api: str = "Windows WASAPI",
    inputs: int = 0,
    outputs: int = 0,
) -> AudioDeviceInfo:
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


class FakeBackend:
    def __init__(
        self,
        devices: list[AudioDeviceInfo],
        *,
        metrics: AudioStreamMetrics | None = None,
        error: str | None = None,
    ) -> None:
        self.devices = devices
        self.metrics = metrics or AudioStreamMetrics(
            actual_sample_rate=48_000,
            input_latency_ms=5,
            output_latency_ms=6,
            peak_input_level=0.42,
            callback_status_count=0,
        )
        self.error = error
        self.validated: tuple[int, int, int] | None = None

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        return list(self.devices)

    def validate_settings(self, input_device, output_device, request) -> None:  # noqa: ANN001
        if self.error:
            raise RuntimeError(self.error)
        self.validated = (input_device.device_id, output_device.device_id, request.input_channel)

    def run_monitor_probe(self, input_device, output_device, request) -> AudioStreamMetrics:  # noqa: ANN001
        if self.error:
            raise RuntimeError(self.error)
        return self.metrics


def _scarlett_devices() -> list[AudioDeviceInfo]:
    return [
        _device(2, "Scarlett 2i2 USB Input", inputs=2),
        _device(3, "Scarlett 2i2 USB Output", outputs=2),
        _device(4, "Scarlett 2i2 Loopback", inputs=2, outputs=2),
        _device(9, "Laptop Microphone", inputs=2),
    ]


def test_resolver_selects_physical_scarlett_and_excludes_loopback() -> None:
    input_device, output_device = resolve_scarlett_2i2_devices(
        _scarlett_devices(),
        input_channel=2,
    )
    assert input_device.device_id == 2
    assert output_device.device_id == 3


def test_channel_two_requires_two_input_channels() -> None:
    backend = FakeBackend(_scarlett_devices())
    result = qualify_scarlett_2i2(backend, AudioProbeRequest(input_channel=2))
    assert result.qualified is True
    assert result.low_latency_ready is True
    assert backend.validated == (2, 3, 2)
    assert result.metrics is not None
    assert result.metrics.peak_input_level == 0.42


def test_high_latency_is_reported_without_hiding_functional_success() -> None:
    backend = FakeBackend(
        _scarlett_devices(),
        metrics=AudioStreamMetrics(
            actual_sample_rate=48_000,
            input_latency_ms=18,
            output_latency_ms=20,
            peak_input_level=0.2,
            callback_status_count=0,
        ),
    )
    result = qualify_scarlett_2i2(backend, AudioProbeRequest(low_latency_target_ms=25))
    assert result.qualified is True
    assert result.low_latency_ready is False
    assert any("latency exceeds" in warning for warning in result.warnings)


def test_callback_status_events_are_visible() -> None:
    backend = FakeBackend(
        _scarlett_devices(),
        metrics=AudioStreamMetrics(
            actual_sample_rate=48_000,
            input_latency_ms=4,
            output_latency_ms=5,
            peak_input_level=0.1,
            callback_status_count=2,
        ),
    )
    result = qualify_scarlett_2i2(backend, AudioProbeRequest())
    assert result.qualified is True
    assert any("2 callback status" in warning for warning in result.warnings)


def test_missing_or_unsupported_scarlett_fails_closed() -> None:
    result = qualify_scarlett_2i2(
        FakeBackend([_device(1, "Laptop Microphone", inputs=2)]),
        AudioProbeRequest(),
    )
    assert result.qualified is False
    assert "Scarlett" in result.errors[0]

    failed = qualify_scarlett_2i2(
        FakeBackend(_scarlett_devices(), error="sample rate unsupported"),
        AudioProbeRequest(),
    )
    assert failed.qualified is False
    assert failed.errors == ["sample rate unsupported"]


def test_reenumeration_tolerates_windows_device_id_changes() -> None:
    first_input, first_output = resolve_scarlett_2i2_devices(_scarlett_devices(), input_channel=1)
    renumbered = [
        _device(21, first_input.name, inputs=2),
        _device(22, first_output.name, outputs=2),
    ]
    second_input, second_output = resolve_scarlett_2i2_devices(renumbered, input_channel=1)
    assert (second_input.device_id, second_output.device_id) == (21, 22)
