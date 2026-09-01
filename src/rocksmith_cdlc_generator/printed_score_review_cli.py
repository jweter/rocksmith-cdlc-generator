from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk

from .printed_score_review_ui import PrintedScoreReviewWindow


def main(argv: list[str] | None = None) -> int:
    """Run the private printed-score review window and exit when that window closes.

    The product desktop owns its own Tk main loop. This standalone command instead
    creates a hidden root and waits specifically for the review Toplevel. Waiting on
    that window avoids leaving an invisible root process alive after the reviewer
    clicks Close.
    """

    parser = argparse.ArgumentParser(
        prog="cdlc-score-review",
        description="Review private printed-score recognition candidates measure by measure",
    )
    parser.add_argument("project", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--bpm", type=float, default=80.0)
    args = parser.parse_args(argv)

    root = tk.Tk()
    root.withdraw()
    try:
        window = PrintedScoreReviewWindow(
            root,
            args.project,
            args.candidates,
            default_bpm=args.bpm,
        )
        window.focus_force()
        root.wait_window(window)
    except Exception as exc:
        raise SystemExit(f"Could not open printed-score review: {exc}") from exc
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
