from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rocksmith_cdlc_generator.tone_corpus_diagnostics import diagnose_similarity, summarize_library
from rocksmith_cdlc_generator.tone_reference_library import read_library


def main() -> int:
    parser = argparse.ArgumentParser(description="Report private local Rocksmith tone-library statistics and explain reference matches.")
    parser.add_argument("library", type=Path)
    parser.add_argument("--arrangement", choices=("lead", "rhythm", "bass"))
    parser.add_argument("--device-key", action="append", default=[])
    parser.add_argument("--descriptor", action="append", default=[])
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    library = read_library(args.library)
    payload: dict[str, object] = {"stats": asdict(summarize_library(library))}
    if args.arrangement:
        payload["matches"] = [
            {
                "score": item.score,
                "authority_weight": item.authority_weight,
                "key_overlap": item.key_overlap,
                "descriptor_overlap": item.descriptor_overlap,
                "matched_device_keys": item.matched_device_keys,
                "matched_descriptors": item.matched_descriptors,
                "source_type": item.tone.source_type,
                "artist": item.tone.artist,
                "title": item.tone.title,
                "arrangement": item.tone.arrangement,
                "tone_key": item.tone.tone_key,
                "tone_name": item.tone.tone_name,
                "fingerprint": item.tone.fingerprint,
            }
            for item in diagnose_similarity(
                library,
                arrangement=args.arrangement,
                device_keys=set(args.device_key),
                descriptors=set(args.descriptor),
                limit=args.limit,
            )
        ]
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
