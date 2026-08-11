from __future__ import annotations

import argparse

from rocksmith_cdlc_generator.audio_io import AudioProbeRequest, resolve_scarlett_2i2_devices
from rocksmith_cdlc_generator.audition_dsp import ReferenceAuditionProcessor
from rocksmith_cdlc_generator.experimental_live_tone import (
    EXPERIMENTAL_LIVE_TONE_PRESETS,
    build_experimental_live_tone_preset,
    classify_input_level,
)
from rocksmith_cdlc_generator.sounddevice_backend import SoundDeviceBackend


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Experimental first-playable live guitar tone test through native Focusrite ASIO. "
            "No audio is recorded or written to disk."
        )
    )
    parser.add_argument(
        "--preset",
        choices=tuple(EXPERIMENTAL_LIVE_TONE_PRESETS),
        default="crunch",
    )
    parser.add_argument("--input-channel", type=int, choices=(1, 2), default=1)
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--sample-rate", type=float, default=48_000)
    parser.add_argument(
        "--device-name",
        default="Focusrite USB ASIO",
        help="Required native ASIO device-name substring.",
    )
    parser.add_argument(
        "--acknowledge-asio-buffer-may-change",
        action="store_true",
        help=(
            "Required acknowledgement that the current PortAudio ASIO adapter may change the "
            "Focusrite control-panel buffer. Restore your preferred buffer after the test if needed."
        ),
    )
    args = parser.parse_args()

    if not args.acknowledge_asio_buffer_may_change:
        parser.error(
            "experimental native ASIO audition is blocked unless "
            "--acknowledge-asio-buffer-may-change is supplied"
        )

    chain = build_experimental_live_tone_preset(args.preset)
    if int(args.sample_rate) != chain.sample_rate_hz:
        parser.error(f"preset expects {chain.sample_rate_hz} Hz")

    print("EXPERIMENTAL LIVE TONE TEST")
    print("No audio will be saved.")
    print("WARNING: PortAudio may change the Focusrite ASIO buffer during this test.")
    print("Set Direct Monitor OFF so you hear the processed software path rather than dry hardware monitoring.")
    print(f"Preset: {chain.name}")

    backend = SoundDeviceBackend(
        enable_asio=True,
        allow_asio_buffer_negotiation=True,
    )
    request = AudioProbeRequest(
        input_channel=args.input_channel,
        sample_rate=args.sample_rate,
        duration_seconds=args.seconds,
        preferred_host_api="ASIO",
        preferred_device_name=args.device_name,
        require_preferred_path=True,
    )
    input_device, output_device = resolve_scarlett_2i2_devices(
        backend.enumerate_devices(),
        input_channel=args.input_channel,
        request=request,
    )
    backend.validate_settings(input_device, output_device, request)

    processor = ReferenceAuditionProcessor()
    metrics = backend.run_processed_monitor_probe(
        input_device,
        output_device,
        request,
        process_block=lambda samples: processor.process(samples, chain),
    )

    print(f"Selected: {input_device.name} [{input_device.host_api}]")
    print(f"Round-trip latency: {metrics.roundtrip_latency_ms:.2f} ms")
    print(f"Peak input level: {metrics.peak_input_level:.4f}")
    input_level_status = classify_input_level(metrics.peak_input_level)
    print(f"Input level status: {input_level_status.upper()}")
    if input_level_status == "clipping":
        print(
            "WARNING: input reached digital full scale. Lower the Scarlett input gain before "
            "judging tone quality; clipping at capture cannot be repaired by downstream DSP."
        )
    elif input_level_status == "hot":
        print(
            "WARNING: input is very hot. Consider lowering the Scarlett input gain to leave "
            "more headroom for strong picking."
        )
    if metrics.callback_frames_min is not None:
        if metrics.callback_frames_min == metrics.callback_frames_max:
            print(f"Observed callback frames: {metrics.callback_frames_min}")
        else:
            print(
                "Observed callback frames: "
                f"{metrics.callback_frames_min}-{metrics.callback_frames_max}"
            )
    if metrics.callback_status_count:
        print(f"WARNING: {metrics.callback_status_count} callback status event(s) occurred")
    print("Test complete. Check Focusrite Device Settings and restore your preferred buffer if it changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
