from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.local_tone_batch import (
    load_explicit_source_map,
    scan_changed_psarcs,
    source_resolver_from_map,
    write_batch_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally index changed local Rocksmith PSARCs into the private tone-reference library."
    )
    parser.add_argument("--rocksmith-root", type=Path, required=True)
    parser.add_argument("--dlc-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-map", type=Path, default=None)
    parser.add_argument(
        "--default-source-type",
        choices=("official_rocksmith", "custom_dlc", "user_created", "unknown"),
        default="unknown",
        help="Applied only when an exact package path is absent from --source-map. Defaults to unknown; no authority is inferred.",
    )
    parser.add_argument("--bridge", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Maximum changed packages to process in this run")
    args = parser.parse_args()

    mapping = load_explicit_source_map(args.source_map)
    resolver = source_resolver_from_map(args.dlc_root, mapping, default=args.default_source_type)
    report = scan_changed_psarcs(
        dlc_root=args.dlc_root,
        rocksmith_root=args.rocksmith_root,
        workspace_root=args.workspace_root,
        library_path=args.library,
        source_resolver=resolver,
        bridge_path=args.bridge,
        limit=args.limit,
    )
    write_batch_report(report, args.report)
    print(
        f"Planned {report.planned_count} changed packages: "
        f"{report.succeeded_count} indexed, {report.failed_count} failed."
    )
    if report.failed_count:
        for result in report.results:
            if result.status == "failed":
                print(f"FAILED {Path(result.path).name}: {result.error_type}: {result.error_message}")


if __name__ == "__main__":
    main()
