"""Offline compare against auto-cdlc output; intentionally never promotes musical authority."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .auto_cdlc_oracle import AutoCdlcOracleError, compare_auto_cdlc_export


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-auto-cdlc-oracle",
        description=(
            "Compare local auto-cdlc MIDI and SVL output with our raw Bass transcription "
            "and beat grid. Normalizes upstream's padded four-beat COUNT clock; does not "
            "accept charts, upload song data or install Rocksmith packages."
        ),
    )
    parser.add_argument("--project", type=Path, required=True, help="Our already analyzed project directory")
    parser.add_argument("--upstream-dir", type=Path, required=True, help="Folder containing exactly one upstream .mid, .svl and diagnostico.json")
    parser.add_argument("--upstream-audio", type=Path, required=True, help="Original recording given to upstream, checked against immutable project source SHA-256")
    parser.add_argument("--out", type=Path, required=True, help="Local aggregate-only report destination outside the Git checkout")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        report = compare_auto_cdlc_export(
            args.project,
            args.upstream_dir,
            upstream_audio=args.upstream_audio,
            out_path=args.out,
        )
    except (AutoCdlcOracleError, ValueError, OSError) as exc:
        print(f"auto-cdlc oracle error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("Comparison complete. Verdict: REVIEW_REQUIRED (secondary unverified oracle).")
    print("Alerts: " + (", ".join(report["alerts"]) if report["alerts"] else "none"))
    print(f"Sanitized local report: {args.out.expanduser().resolve()}")
    raise SystemExit(3)


if __name__ == "__main__":
    main()
