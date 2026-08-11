from __future__ import annotations

import importlib
import os
from collections.abc import Callable

from .audio_io import AudioDeviceInfo, AudioProbeRequest, AudioStreamMetrics


class SoundDeviceBackend:
    """Optional PortAudio-backed adapter used only for explicit local hardware probes."""

    def __init__(
        self,
        *,
        enable_asio: bool = False,
        wasapi_exclusive: bool = False,
        allow_asio_buffer_negotiation: bool = False,
    ) -> None:
        if enable_asio:
            os.environ.setdefault("SD_ENABLE_ASIO", "1")
        try:
            self._sd = importlib.import_module("sounddevice")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "python-sounddevice is not installed; install the optional audio dependency"
            ) from exc
        self._wasapi_exclusive = wasapi_exclusive
        self._allow_asio_buffer_negotiation = allow_asio_buffer_negotiation
        self._wasapi_input_settings = None
        self._wasapi_output_settings = None
        if wasapi_exclusive:
            self._wasapi_input_settings = self._sd.WasapiSettings(exclusive=True)
            self._wasapi_output_settings = self._sd.WasapiSettings(exclusive=True)

    def enumerate_devices(self) -> list[AudioDeviceInfo]:
        host_apis = self._sd.query_hostapis()
        result: list[AudioDeviceInfo] = []
        for item in self._sd.query_devices():
            host_api_index = int(item["hostapi"])
            host_api_name = str(host_apis[host_api_index]["name"])
            result.append(
                AudioDeviceInfo(
                    device_id=int(item["index"]),
                    name=str(item["name"]),
                    host_api=host_api_name,
                    max_input_channels=int(item["max_input_channels"]),
                    max_output_channels=int(item["max_output_channels"]),
                    default_sample_rate=float(item["default_samplerate"]),
                    default_low_input_latency=float(item["default_low_input_latency"]),
                    default_low_output_latency=float(item["default_low_output_latency"]),
                )
            )
        return result

    def _assert_wasapi_path(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
    ) -> None:
        if not self._wasapi_exclusive:
            return
        if "wasapi" not in input_device.host_api.casefold():
            raise RuntimeError(
                "WASAPI exclusive mode requires a Windows WASAPI input endpoint; "
                f"selected {input_device.name} [{input_device.host_api}]"
            )
        if "wasapi" not in output_device.host_api.casefold():
            raise RuntimeError(
                "WASAPI exclusive mode requires a Windows WASAPI output endpoint; "
                f"selected {output_device.name} [{output_device.host_api}]"
            )

    @staticmethod
    def _uses_asio_driver_buffer(
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
    ) -> bool:
        return (
            input_device.host_api.casefold() == "asio"
            and output_device.host_api.casefold() == "asio"
        )

    def _assert_asio_negotiation_allowed(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
    ) -> None:
        if not self._uses_asio_driver_buffer(input_device, output_device):
            return
        if self._allow_asio_buffer_negotiation:
            return
        raise RuntimeError(
            "native ASIO stream opening is blocked by default because PortAudio may negotiate "
            "and change the vendor driver's control-panel buffer size; enumeration is safe, "
            "or explicitly opt in with --allow-asio-buffer-negotiation for a controlled test"
        )

    def validate_settings(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
        request: AudioProbeRequest,
    ) -> None:
        self._assert_wasapi_path(input_device, output_device)
        self._sd.check_input_settings(
            device=input_device.device_id,
            channels=request.input_channel,
            dtype="float32",
            samplerate=request.sample_rate,
            extra_settings=self._wasapi_input_settings,
        )
        self._sd.check_output_settings(
            device=output_device.device_id,
            channels=2,
            dtype="float32",
            samplerate=request.sample_rate,
            extra_settings=self._wasapi_output_settings,
        )

    def _stream_blocksize(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
        request: AudioProbeRequest,
    ) -> int:
        return 0 if self._uses_asio_driver_buffer(input_device, output_device) else request.block_size

    def _finish_metrics(
        self,
        *,
        stream,
        peak_input_level: float,
        callback_status_count: int,
        callback_frames_min: int | None,
        callback_frames_max: int | None,
    ) -> AudioStreamMetrics:
        latency = stream.latency
        if isinstance(latency, tuple):
            input_latency, output_latency = latency
        else:
            input_latency = output_latency = float(latency)
        return AudioStreamMetrics(
            actual_sample_rate=float(stream.samplerate),
            input_latency_ms=float(input_latency) * 1000,
            output_latency_ms=float(output_latency) * 1000,
            peak_input_level=peak_input_level,
            callback_status_count=callback_status_count,
            callback_frames_min=callback_frames_min,
            callback_frames_max=callback_frames_max,
        )

    def run_monitor_probe(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
        request: AudioProbeRequest,
    ) -> AudioStreamMetrics:
        return self.run_processed_monitor_probe(
            input_device,
            output_device,
            request,
            process_block=lambda samples: samples,
        )

    def run_processed_monitor_probe(
        self,
        input_device: AudioDeviceInfo,
        output_device: AudioDeviceInfo,
        request: AudioProbeRequest,
        *,
        process_block: Callable[[list[float]], list[float]],
    ) -> AudioStreamMetrics:
        """Monitor one instrument input through a caller-supplied local DSP block.

        The callback is intentionally mono-in/stereo-out and writes no audio to disk.
        Native ASIO remains guarded by the explicit buffer-negotiation opt-in.
        """
        self._assert_wasapi_path(input_device, output_device)
        self._assert_asio_negotiation_allowed(input_device, output_device)
        input_channels = request.input_channel
        selected_channel = request.input_channel - 1
        peak_input_level = 0.0
        callback_status_count = 0
        callback_frames_min: int | None = None
        callback_frames_max: int | None = None

        def callback(indata, outdata, frames, time_info, status) -> None:  # noqa: ANN001
            nonlocal peak_input_level, callback_status_count
            nonlocal callback_frames_min, callback_frames_max
            if status:
                callback_status_count += 1
            callback_frames_min = frames if callback_frames_min is None else min(callback_frames_min, frames)
            callback_frames_max = frames if callback_frames_max is None else max(callback_frames_max, frames)
            source = memoryview(indata).cast("f")
            target = memoryview(outdata).cast("f")
            mono: list[float] = []
            local_peak = 0.0
            for frame in range(frames):
                sample = float(source[frame * input_channels + selected_channel])
                mono.append(sample)
                local_peak = max(local_peak, abs(sample))

            processed = process_block(mono)
            if len(processed) != frames:
                raise ValueError("live audition processor must return one sample per input frame")
            for frame, sample in enumerate(processed):
                target[frame * 2] = sample
                target[frame * 2 + 1] = sample
            peak_input_level = max(peak_input_level, local_peak)

        # Even with blocksize=0, observed Focusrite hardware testing showed
        # PortAudio/ASIO can renegotiate the vendor control-panel buffer. This
        # path therefore requires an explicit opt-in above; blocksize=0 only
        # avoids requesting a particular callback size from this adapter.
        stream = self._sd.RawStream(
            device=(input_device.device_id, output_device.device_id),
            samplerate=request.sample_rate,
            blocksize=self._stream_blocksize(input_device, output_device, request),
            channels=(input_channels, 2),
            dtype=("float32", "float32"),
            latency="low",
            extra_settings=(self._wasapi_input_settings, self._wasapi_output_settings),
            callback=callback,
        )
        with stream:
            self._sd.sleep(int(request.duration_seconds * 1000))
            return self._finish_metrics(
                stream=stream,
                peak_input_level=peak_input_level,
                callback_status_count=callback_status_count,
                callback_frames_min=callback_frames_min,
                callback_frames_max=callback_frames_max,
            )
