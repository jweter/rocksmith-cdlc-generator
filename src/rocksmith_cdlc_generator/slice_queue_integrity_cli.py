"""Inspect an explicitly saved copy of the public #796 queue; no network actions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .slice_queue_integrity import SliceQueueIntegrityError, inspect_slice_queue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-slice-queue-validate",
        description=(
            "Validate a local Markdown copy of the next-62 Rocksmith issue. "
            "This checks structure only; checkboxes are not independent merge "
            "proof and do not authorize code, model or release actions."
        ),
    )
    parser.add_argument("--issue-markdown", required=True, type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        body = args.issue_markdown.read_text(encoding="utf-8")
        result = inspect_slice_queue(body)
    except (OSError, UnicodeError, SliceQueueIntegrityError) as exc:
        # Public issue source path still need not be printed in diagnostics.
        code = str(exc) if isinstance(exc, SliceQueueIntegrityError) else "QUEUE_INPUT_UNREADABLE"
        print(json.dumps({"status": "BLOCKED", "reason": code}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(result.public_dict(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
