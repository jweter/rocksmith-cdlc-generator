"""Offline CLI plumbing around the corpus differential comparator (issue #693 slice 6).

The private regression lane runs on the owner's machine, outside this repository, against a
real installed-library corpus this project never sees. This module is the sanitization boundary
between that private input and anything that could end up in the repository or an evidence
ledger: it loads two caller-supplied note files, calls ``corpus_differential.compare_arrangements``,
and returns a report containing nothing but ``CorpusDifferential.sanitized()``, the lane, the
SHA-256 of each input file, and the repository build identity. No note data, file path, title,
or other input content is ever included in that report.

The lane is a second axis independent of trust tier. Trust tier says how much authority the
*reference* carries. Lane says what the *generated* side actually is: a true generator output
(``independent_generation``) or notes the importer extracted from a score
(``importer_fidelity``), which measures import correctness, not generation accuracy. Mixing the
two would let importer-fidelity evidence quietly inflate a generation-accuracy claim, so the lane
travels with the report rather than being inferred or discarded.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Literal

from .build_identity import current_build_identity
from .corpus_differential import CorpusDifferential, DiffNote, Thresholds, TrustTier, compare_arrangements
from .hashing import sha256_file

Lane = Literal["independent_generation", "importer_fidelity"]
LANES: tuple[Lane, ...] = ("independent_generation", "importer_fidelity")

_REQUIRED_NOTE_FIELDS = ("onset_seconds", "duration_seconds", "midi")


class CorpusDifferentialHarnessError(ValueError):
    """Malformed input or an unsafe output destination; never raised for a comparator verdict."""


def load_diff_notes(path: Path) -> list[DiffNote]:
    """Load a JSON list of notes (onset_seconds, duration_seconds, midi, optional string/fret).

    Raises ``CorpusDifferentialHarnessError`` with a clear, structural message on any malformed
    input. The message may name the file and field, but never echoes note values back out.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusDifferentialHarnessError(f"cannot read note file {path}: {exc}") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise CorpusDifferentialHarnessError(f"note file {path} is not valid JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise CorpusDifferentialHarnessError(f"note file {path} must contain a JSON list of notes")

    notes: list[DiffNote] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise CorpusDifferentialHarnessError(f"note file {path}: entry {index} must be a JSON object")
        missing = [key for key in _REQUIRED_NOTE_FIELDS if key not in item]
        if missing:
            raise CorpusDifferentialHarnessError(
                f"note file {path}: entry {index} is missing required field(s): {', '.join(missing)}"
            )
        try:
            notes.append(
                DiffNote(
                    onset_seconds=float(item["onset_seconds"]),
                    duration_seconds=float(item["duration_seconds"]),
                    midi=int(item["midi"]),
                    string=None if item.get("string") is None else int(item["string"]),
                    fret=None if item.get("fret") is None else int(item["fret"]),
                )
            )
        except (TypeError, ValueError) as exc:
            raise CorpusDifferentialHarnessError(f"note file {path}: entry {index} has an invalid field: {exc}") from exc
    return notes


def _repository_checkout_root() -> Path | None:
    """The repository checkout this module is running from, or ``None`` if it is not one.

    Mirrors ``build_identity._source_checkout_root``'s ``.git``-gated check: a non-editable
    install (no ``.git`` at the implied root) is not a real checkout, so there is nothing to
    protect and the output guard becomes a no-op rather than blocking an unrelated directory.
    """
    root = Path(__file__).resolve().parents[2]
    return root if (root / ".git").exists() else None


def refuse_output_inside_repository_checkout(output_path: Path) -> None:
    """Raise ``CorpusDifferentialHarnessError`` if ``output_path`` is inside this checkout.

    Private-corpus results must never land somewhere a routine ``git add`` could pick them up.
    """
    root = _repository_checkout_root()
    if root is None:
        return
    resolved = output_path.expanduser().resolve()
    if resolved == root or resolved.is_relative_to(root):
        raise CorpusDifferentialHarnessError(
            f"refusing to write a private-corpus report inside the repository checkout: {resolved}"
        )


def build_report(
    differential: CorpusDifferential,
    *,
    lane: Lane,
    reference_path: Path,
    generated_path: Path,
) -> dict[str, object]:
    """Sanitized report: ``CorpusDifferential.sanitized()`` plus lane, input hashes, build identity."""
    if lane not in LANES:
        raise CorpusDifferentialHarnessError(f"lane must be one of {LANES}, not {lane!r}")
    report = differential.sanitized()
    report["lane"] = lane
    report["input_sha256"] = {
        "reference": sha256_file(reference_path),
        "generated": sha256_file(generated_path),
    }
    report["build_identity"] = asdict(current_build_identity())
    return report


def run_corpus_differential_harness(
    *,
    reference_path: Path,
    generated_path: Path,
    trust_tier: TrustTier,
    lane: Lane,
    out_path: Path,
    thresholds: Thresholds = Thresholds(),
) -> tuple[CorpusDifferential, dict[str, object], Path]:
    """Load both note files, compare them, and write the sanitized report to ``out_path``.

    Returns the comparator result, the written report, and the resolved output path. The output
    guard runs before either input file is read, so a misconfigured destination never causes a
    private note file to be opened at all.
    """
    if lane not in LANES:
        raise CorpusDifferentialHarnessError(f"lane must be one of {LANES}, not {lane!r}")
    refuse_output_inside_repository_checkout(out_path)

    reference_notes = load_diff_notes(reference_path)
    generated_notes = load_diff_notes(generated_path)

    differential = compare_arrangements(reference_notes, generated_notes, trust_tier=trust_tier, thresholds=thresholds)
    report = build_report(differential, lane=lane, reference_path=reference_path, generated_path=generated_path)

    resolved_out = out_path.expanduser().resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    resolved_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return differential, report, resolved_out
