from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocksmith_cdlc_generator.local_psarc_workspace import copy_psarc_for_inspection


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy one installed Rocksmith PSARC into the private verified inspection workspace.")
    parser.add_argument("psarc", type=Path)
    parser.add_argument("--rocksmith-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    staged = copy_psarc_for_inspection(
        args.psarc,
        workspace_root=args.workspace,
        rocksmith_root=args.rocksmith_root,
    )
    print(json.dumps({
        "source": str(staged.source),
        "copy": str(staged.copy),
        "source_sha256": staged.source_sha256,
        "copy_sha256": staged.copy_sha256,
        "verified": staged.verified,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
