from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class AudioDeviceInfo(BaseModel):
    device_id: int
    name: str
    host_api: str
    max_input_channels: int = Field(ge=0)
    max_output_channels: int = Field(ge=0)
    default_sample_rate: float = Field(gt=0)
    default_low_input_latency: float = Field(ge=0)
    default_low_output_latency: float = Field(ge=0)


class AudioProbeRequest(BaseModel):
    input_channel: int = Field(default=1, ge=1, le=2)
    sample_rate: float = Field(default=48_000, gt=0)
    block_size: int = Field(default=128, gt=0)
    duration_seconds: float = Field(default=2.0, gt=0, le=30.0)
    low_latency_target_ms: float = Field(default=25.0, gt=0)
    preferred_host_api: str | None = None
    preferred_device_name: str | None = None
    require_preferred_path: bool = False


class AudioStreamMetrics(BaseModel):
    actual_sample_rate: float = Field(gt=0)
    input_latency_ms: float = Field(ge=0)
    output_latency_ms: float = Field(ge=0)
    peak_input_level: float = Field(ge=0)
    callback_status_count: int = Field(ge=0)

    @property
    def roundtrip_latency_ms(self) -> float:
        return self.input_latency_ms + self.output_latency_ms


class ScarlettQualificationResult(BaseModel):
    qualified: bool
    low_latency_ready: bool
    input_device: AudioDeviceInfo | None = None
    output_device: AudioDeviceInfo | None = None
    request: AudioProbeRequest
    metrics: AudioStreamMetrics | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AudioBackend(Protocol):
    def enumerate_devices(self) -> list[AudioDeviceInfo]: ...

    def validate_settings(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
        request: AudioProbeRequest,
    ) -> None: ...

    def run_monitor_probe(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
        request: AudioProbeRequest,
    ) -> AudioStreamMetrics: ...


def _scarlett_score(device: AudioDeviceInfo) -> int:
    text = f"{device.name} {device.host_api}".casefold()
    if "loopback" in text:
        return -1
    score = 0
    if "scarlett" in text:
        score += 4
    if "2i2" in text:
        score += 4
    if "focusrite" in text:
        score += 2
    if "asio" in text:
        score += 1
    return score


def _matches_preference(device: AudioDeviceInfo, request: AudioProbeRequest) -> bool:
    if request.preferred_host_api and request.preferred_host_api.casefold() not in device.host_api.casefold():
        return False
    if request.preferred_device_name and request.preferred_device_name.casefold() not in device.name.casefold():
        return False
    return True


def _preferred_pair_score(device: AudioDeviceInfo) -> tuple[int, float, int]:
    return (
        _scarlett_score(device),
        -(device.default_low_input_latency + device.default_low_output_latency),
        -device.device_id,
    )


def resolve_scarlett_2i2_devices(
    devices: list[AudioDeviceInfo],
    *,
    input_channel: int,
    request: AudioProbeRequest | None = None,
) -> tuple[AudioDeviceInfo, AudioDeviceInfo]:
    """Resolve current Scarlett endpoints or an explicitly requested audio path."""
    request = request or AudioProbeRequest(input_channel=input_channel)

    if request.preferred_device_name or request.preferred_host_api:
        preferred = [item for item in devices if _matches_preference(item, request)]
        duplex = [
            item
            for item in preferred
            if item.max_input_channels >= input_channel and item.max_output_channels >= 2
        ]
        if duplex:
            duplex.sort(
                key=lambda item: (
                    item.default_low_input_latency + item.default_low_output_latency,
                    item.device_id,
                )
            )
            return duplex[0], duplex[0]

        # Windows commonly exposes a physical interface as separate WASAPI
        # capture/render endpoints rather than one full-duplex device. When the
        # preference is host-API-only, keep the pair bound to Scarlett/Focusrite
        # endpoints so strict selection cannot accidentally mix in laptop audio.
        preferred_inputs = [
            item
            for item in preferred
            if item.max_input_channels >= input_channel
            and (request.preferred_device_name is not None or _scarlett_score(item) > 0)
        ]
        preferred_outputs = [
            item
            for item in preferred
            if item.max_output_channels >= 2
            and (request.preferred_device_name is not None or _scarlett_score(item) > 0)
        ]
        if preferred_inputs and preferred_outputs:
            preferred_inputs.sort(key=_preferred_pair_score, reverse=True)
            preferred_outputs.sort(key=_preferred_pair_score, reverse=True)
            return preferred_inputs[0], preferred_outputs[0]

        if request.require_preferred_path:
            target = request.preferred_device_name or request.preferred_host_api or "requested"
            raise ValueError(
                "required audio path was not found as either a full-duplex endpoint "
                f"or a matched input/output pair: {target}"
            )

    inputs = [
        item
        for item in devices
        if item.max_input_channels >= input_channel and _scarlett_score(item) > 0
    ]
    outputs = [
        item
        for item in devices
        if item.max_output_channels >= 2 and _scarlett_score(item) > 0
    ]
    if not inputs:
        raise ValueError("no Scarlett 2i2/Focusrite input endpoint with the requested channel was found")
    if not outputs:
        raise ValueError("no Scarlett 2i2/Focusrite stereo output endpoint was found")

    inputs.sort(key=lambda item: (_scarlett_score(item), item.max_input_channels), reverse=True)
    outputs.sort(key=lambda item: (_scarlett_score(item), item.max_output_channels), reverse=True)
    return inputs[0], outputs[0]


def qualify_scarlett_2i2(
    backend: AudioBackend,
    request: AudioProbeRequest,
) -> ScarlettQualificationResult:
    """Run one explicit, non-recording Scarlett monitor qualification probe."""
    try:
        input_device, output_device = resolve_scarlett_2i2_devices(
            backend.enumerate_devices(),
            input_channel=request.input_channel,
            request=request,
        )
    except Exception as exc:
        return ScarlettQualificationResult(
            qualified=False,
            low_latency_ready=False,
            request=request,
            errors=[str(exc)],
        )

    warnings: list[str] = []
    try:
        backend.validate_settings(input_device, output_device, request)
        metrics = backend.run_monitor_probe(input_device, output_device, request)
    except Exception as exc:
        return ScarlettQualificationResult(
            qualified=False,
            low_latency_ready=False,
            input_device=input_device,
            output_device=output_device,
            request=request,
            errors=[str(exc)],
        )

    low_latency_ready = metrics.roundtrip_latency_ms <= request.low_latency_target_ms
    if not low_latency_ready:
        warnings.append(
            "functional audio I/O passed, but measured/reported round-trip latency exceeds "
            f"the {request.low_latency_target_ms:g} ms audition target"
        )
    if metrics.callback_status_count:
        warnings.append(
            f"PortAudio reported {metrics.callback_status_count} callback status event(s) during the probe"
        )

    return ScarlettQualificationResult(
        qualified=True,
        low_latency_ready=low_latency_ready,
        input_device=input_device,
        output_device=output_device,
        request=request,
        metrics=metrics,
        warnings=warnings,
    )
