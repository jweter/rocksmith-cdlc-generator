from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.audio_io import AudioProbeRequest, qualify_scarlett_2i2
from rocksmith_cdlc_generator.sounddevice_backend import SoundDeviceBackend


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly enumerate and qualify a local Scarlett 2i2 for live tone audition."
    )
    parser.add_argument("--input-channel", type=int, choices=(1, 2), default=1)
    parser.add_argument("--sample-rate", type=float, default=48_000)
    parser.add_argument("--block-size", type=int, default=128)
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--latency-target-ms", type=float, default=25.0)
    parser.add_argument(
        "--enable-asio",
        action="store_true",
        help="Ask python-sounddevice to expose ASIO host APIs on Windows.",
    )
    parser.add_argument(
        "--host-api",
        help="Prefer a host API such as ASIO. Use with --require-selected-path to forbid fallback.",
    )
    parser.add_argument(
        "--device-name",
        help="Prefer a full-duplex device name substring, e.g. 'ASIO4ALL v2'.",
    )
    parser.add_argument(
        "--require-selected-path",
        action="store_true",
        help="Fail instead of falling back when the requested host API/device is unavailable.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Required to open the audio stream and monitor the selected input briefly.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("private/audio-io/scarlett-2i2-qualification.json"),
        help="Ignored private path for the qualification report.",
    )
    args = parser.parse_args()

    backend = SoundDeviceBackend(enable_asio=args.enable_asio)
    devices = backend.enumerate_devices()
    print("Available audio endpoints:")
    for item in devices:
        print(
            f"  {item.device_id}: {item.name} [{item.host_api}] "
            f"({item.max_input_channels} in / {item.max_output_channels} out)"
        )

    if not args.run:
        print("\nEnumeration only. Re-run with --run to perform the explicit monitoring probe.")
        return 0

    request = AudioProbeRequest(
        input_channel=args.input_channel,
        sample_rate=args.sample_rate,
        block_size=args.block_size,
        duration_seconds=args.seconds,
        low_latency_target_ms=args.latency_target_ms,
        preferred_host_api=args.host_api,
        preferred_device_name=args.device_name,
        require_preferred_path=args.require_selected_path,
    )
    result = qualify_scarlett_2i2(backend, request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    print(f"\nQualification report: {args.output}")
    print(f"Functional I/O: {'PASS' if result.qualified else 'FAIL'}")
    print(f"Low-latency target: {'PASS' if result.low_latency_ready else 'NOT YET'}")
    if result.input_device is not None:
        print(
            f"Selected input: {result.input_device.name} "
            f"[{result.input_device.host_api}] (id {result.input_device.device_id})"
        )
    if result.output_device is not None:
        print(
            f"Selected output: {result.output_device.name} "
            f"[{result.output_device.host_api}] (id {result.output_device.device_id})"
        )
    if result.metrics is not None:
        print(f"Reported round-trip latency: {result.metrics.roundtrip_latency_ms:.2f} ms")
        print(f"Peak input level: {result.metrics.peak_input_level:.4f}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")
    return 0 if result.qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
