from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.local_tone_indexer import index_local_psarc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index one installed Rocksmith PSARC into the private local tone-reference library."
    )
    parser.add_argument("source", type=Path, help="Installed .psarc under the configured Rocksmith root")
    parser.add_argument("--rocksmith-root", type=Path, required=True)
    parser.add_argument("--dlc-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument(
        "--source-type",
        choices=("official_rocksmith", "custom_dlc", "user_created", "unknown"),
        required=True,
        help="Authority class supplied explicitly; never inferred from ambiguous package metadata.",
    )
    parser.add_argument("--bridge", type=Path, default=None)
    args = parser.parse_args()

    library = index_local_psarc(
        args.source,
        dlc_root=args.dlc_root,
        rocksmith_root=args.rocksmith_root,
        workspace_root=args.workspace_root,
        library_path=args.library,
        source_type=args.source_type,
        bridge_path=args.bridge,
    )
    print(
        f"Indexed {args.source.name}: {len(library.tones)} total tone references "
        f"across {len(library.psarcs)} packages."
    )


if __name__ == "__main__":
    main()
