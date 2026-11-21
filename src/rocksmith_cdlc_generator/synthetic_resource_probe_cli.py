"""Read-only-by-default CLI for a fixed synthetic subprocess RAM probe."""
from __future__ import annotations

import argparse
import json

from .auto_cdlc_readiness import available_memory_gib
from .synthetic_resource_probe import run_synthetic_resource_probe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-synthetic-ram-probe",
        description=(
            "Test local process memory monitoring using a fixed stdlib-only "
            "synthetic child. Never run an audio model, source audio or network operation."
        ),
    )
    parser.add_argument("--run-synthetic", action="store_true",
                        help="Opt in to short, fixed-code synthetic RAM workload")
    parser.add_argument("--allocation-mib", type=int, default=8)
    parser.add_argument("--limit-mib", type=int, default=128)
    parser.add_argument("--hold-ms", type=int, default=350)
    parser.add_argument("--max-runtime-seconds", type=float, default=None,
                        help="Explicit bounded deadline for synthetic probe (0.25–10s); default is hold plus startup headroom")
    parser.add_argument("--minimum-available-ram-gib", type=float, default=.5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.run_synthetic:
        try:
            memory = available_memory_gib()
        except (OSError, ValueError):
            memory = None
        print(json.dumps({
            "status": "READINESS_ONLY",
            "available_physical_ram_gib": round(memory, 3) if memory is not None else None,
            "run_requires_explicit_flag": "--run-synthetic",
            "model_execution_proven": False,
            "network_isolation_proven": False,
            "separator_quality_proven": False,
        }, sort_keys=True, indent=2))
        return
    try:
        report = run_synthetic_resource_probe(
            allocation_mib=args.allocation_mib,
            process_limit_mib=args.limit_mib,
            hold_ms=args.hold_ms,
            max_runtime_seconds=args.max_runtime_seconds,
            minimum_available_ram_gib=args.minimum_available_ram_gib,
        )
    except ValueError:
        raise SystemExit("INVALID_SYNTHETIC_PROBE_BOUNDS") from None
    print(json.dumps(report.public_dict(), sort_keys=True, indent=2))
    if report.status != "SYNTHETIC_ONLY_PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
