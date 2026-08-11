from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_catalog import load_toolkit_pedals2014, write_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a locally derived Rocksmith 2014 tone-device catalog")
    parser.add_argument("--pedals2014", required=True, type=Path, help="Toolkit pedals2014.json generated from the user's Rocksmith 2014 gear manifests")
    parser.add_argument("--output", required=True, type=Path, help="Destination normalized catalog JSON")
    args = parser.parse_args()

    catalog = load_toolkit_pedals2014(args.pedals2014)
    destination = write_catalog(catalog, args.output)
    print(destination)
    print(catalog.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
