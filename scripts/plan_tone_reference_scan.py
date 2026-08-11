from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_library import changed_psarcs, read_library


def main() -> int:
    parser = argparse.ArgumentParser(description="List local Rocksmith package files whose tone metadata index needs refresh.")
    parser.add_argument("root", type=Path, help="Local directory containing Rocksmith package files")
    parser.add_argument("--library", type=Path, help="Existing private tone reference library JSON")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    existing = read_library(args.library) if args.library and args.library.is_file() else None
    changed = changed_psarcs(args.root, existing)
    payload = {
        "schema_version": 1,
        "scan_root": str(args.root.resolve()),
        "existing_library": str(args.library.resolve()) if args.library else None,
        "packages_requiring_index_refresh": [str(item.resolve()) for item in changed],
        "count": len(changed),
        "read_only": True,
    }
    rendered = json.dumps(payload, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
