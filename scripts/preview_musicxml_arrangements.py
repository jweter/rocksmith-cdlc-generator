from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.song_preview import load_musicxml_preview_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a trusted MusicXML arrangement manifest as a read-only song preview snapshot."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    snapshot = load_musicxml_preview_snapshot(args.project, args.manifest)
    print(snapshot.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
