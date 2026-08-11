from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.local_tone_batch import load_explicit_source_map, source_resolver_from_map
from rocksmith_cdlc_generator.local_tone_first_scan import run_controlled_first_scan, write_first_scan_report

DEFAULT_ROCKSMITH_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Rocksmith2014")
DEFAULT_DLC_ROOT = DEFAULT_ROCKSMITH_ROOT / "dlc"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small, controlled first scan of a local Rocksmith tone corpus.")
    parser.add_argument("--rocksmith-root", type=Path, default=DEFAULT_ROCKSMITH_ROOT)
    parser.add_argument("--dlc-root", type=Path, default=DEFAULT_DLC_ROOT)
    parser.add_argument("--workspace", type=Path, default=Path("private/rocksmith_library"))
    parser.add_argument("--library", type=Path, default=Path("private/rocksmith_library/tone_reference_library.json"))
    parser.add_argument("--report", type=Path, default=Path("private/rocksmith_library/first_scan_report.json"))
    parser.add_argument("--source-map", type=Path)
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    source_map = load_explicit_source_map(args.source_map)
    resolver = source_resolver_from_map(args.dlc_root, source_map)
    report = run_controlled_first_scan(
        dlc_root=args.dlc_root,
        rocksmith_root=args.rocksmith_root,
        workspace_root=args.workspace,
        library_path=args.library,
        source_resolver=resolver,
        package_limit=args.limit,
        bridge_path=args.bridge,
    )
    destination = write_first_scan_report(report, args.report)
    print(f"first scan report: {destination}")
    print(f"planned={report.batch.planned_count} indexed={report.batch.succeeded_count} failed={report.batch.failed_count}")
    print(f"corpus tones={report.corpus['tone_count']} psarcs={report.corpus['psarc_count']}")


if __name__ == "__main__":
    main()
