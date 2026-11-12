"""Generator-vs-reference differential metrics for the private Rocksmith library corpus (issue #693, slice 5).

Pure and media-free: it compares two lists of note events and returns aggregate numbers, a trust tier and a verdict. It
never sees audio, a PSARC, a path or a title, so its output is safe to write back as sanitized evidence.

Metrics follow the #693 spec: first-event phase, onset phase and drift across the song, pitch and onset agreement,
equivalent pitch under alternate valid string/fret mappings (matching is on MIDI pitch, not on string/fret), and
string/fret agreement reported separately because it is not absolute authority.

Notes are paired by an order-preserving alignment that maximizes the number of equal-pitch pairs and, among equally good
alignments, minimizes total onset error. Pairing each note with its nearest equal-pitch neighbour instead would let a
repeated riff hide a global timing shift (every note pairs with its neighbour and the shift disappears), so it is not used.
Timing is then judged on the fitted phase and drift AND on the residual error of individual notes, so a correct average
clock cannot hide mistimed notes.

The trust tier (A official, B user-trusted, C unverified) is required and carried into the result. A Tier C comparison is
never authoritative: it can inform a developer but cannot by itself pass or fail the generator.

Mutation controls: ``mutate_timing_phase`` and ``mutate_pitch`` build deliberately wrong copies of a generated
arrangement so tests can prove the thresholds detect a timing-phase error and a note error automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from statistics import median
from typing import Literal, Sequence

TrustTier = Literal["A", "B", "C"]
Verdict = Literal["PASS", "FAIL", "REVIEW_REQUIRED"]

ALIGN_WINDOW_SECONDS = 8.0  # the largest onset offset an alignment may bridge: beyond a full bar the arrangements are not comparable
WRONG_PITCH_WINDOW_SECONDS = 0.05  # after removing the global phase, a note this close in time with another pitch is a wrong note


@dataclass(frozen=True)
class DiffNote:
    onset_seconds: float
    duration_seconds: float
    midi: int
    string: int | None = None
    fret: int | None = None

    def __post_init__(self) -> None:
        if not (isfinite(self.onset_seconds) and isfinite(self.duration_seconds)):
            raise ValueError("note times must be finite")
        if self.onset_seconds < 0 or self.duration_seconds < 0:
            raise ValueError("note times must not be negative")


@dataclass(frozen=True)
class Thresholds:
    pass_phase_seconds: float = 0.030
    fail_phase_seconds: float = 0.060
    pass_drift_seconds_per_minute: float = 0.020
    fail_drift_seconds_per_minute: float = 0.050
    pass_jitter_seconds: float = 0.025
    fail_jitter_seconds: float = 0.060
    pass_outlier_fraction: float = 0.05
    fail_outlier_fraction: float = 0.25
    pass_recall: float = 0.95
    fail_recall: float = 0.80
    pass_precision: float = 0.90
    pass_pitch_agreement: float = 0.95
    fail_pitch_agreement: float = 0.80


@dataclass(frozen=True)
class CorpusDifferential:
    trust_tier: TrustTier
    authoritative: bool
    verdict: Verdict
    reasons: tuple[str, ...]
    reference_notes: int
    generated_notes: int
    matched_notes: int
    wrong_pitch_notes: int
    missed_notes: int
    extra_notes: int
    first_event_phase_seconds: float | None
    onset_phase_seconds: float | None
    onset_drift_seconds_per_minute: float | None
    onset_jitter_seconds: float | None
    onset_outlier_fraction: float | None
    recall: float
    precision: float
    pitch_agreement: float
    string_fret_agreement: float | None
    duration_agreement: float | None

    def sanitized(self) -> dict[str, object]:
        """Aggregate numbers only: no notes, no times of individual events, no names or paths."""
        return {
            "trust_tier": self.trust_tier,
            "authoritative": self.authoritative,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "counts": {
                "reference": self.reference_notes,
                "generated": self.generated_notes,
                "matched": self.matched_notes,
                "wrong_pitch": self.wrong_pitch_notes,
                "missed": self.missed_notes,
                "extra": self.extra_notes,
            },
            "first_event_phase_seconds": self.first_event_phase_seconds,
            "onset_phase_seconds": self.onset_phase_seconds,
            "onset_drift_seconds_per_minute": self.onset_drift_seconds_per_minute,
            "onset_jitter_seconds": self.onset_jitter_seconds,
            "onset_outlier_fraction": self.onset_outlier_fraction,
            "recall": self.recall,
            "precision": self.precision,
            "pitch_agreement": self.pitch_agreement,
            "string_fret_agreement": self.string_fret_agreement,
            "duration_agreement": self.duration_agreement,
        }


def _align(reference: Sequence[DiffNote], generated: Sequence[DiffNote]) -> list[tuple[int, int]]:
    """Order-preserving pairs of equal MIDI pitch: most pairs first, then least total onset error.

    A longest-common-subsequence alignment over pitch with a time window. Ties between equally long alignments (the
    ambiguity a repeated riff creates) are broken by the smaller total onset error, never by taking the nearest neighbour.
    """
    n, m = len(reference), len(generated)
    count = [[0] * (m + 1) for _ in range(2)]
    error = [[0.0] * (m + 1) for _ in range(2)]
    step = bytearray((n + 1) * (m + 1))  # 0 start, 1 skip reference, 2 skip generated, 3 pair
    width = m + 1
    for i in range(1, n + 1):
        cur, prev = i % 2, (i - 1) % 2
        ref = reference[i - 1]
        count[cur][0], error[cur][0] = 0, 0.0
        for j in range(1, m + 1):
            best_count, best_error, best_step = count[prev][j], error[prev][j], 1
            left_count, left_error = count[cur][j - 1], error[cur][j - 1]
            if (left_count, -left_error) > (best_count, -best_error):
                best_count, best_error, best_step = left_count, left_error, 2
            gen = generated[j - 1]
            gap = abs(gen.onset_seconds - ref.onset_seconds)
            if gen.midi == ref.midi and gap <= ALIGN_WINDOW_SECONDS:
                diag_count, diag_error = count[prev][j - 1] + 1, error[prev][j - 1] + gap
                if (diag_count, -diag_error) > (best_count, -best_error):
                    best_count, best_error, best_step = diag_count, diag_error, 3
            count[cur][j], error[cur][j] = best_count, best_error
            step[i * width + j] = best_step
    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        move = step[i * width + j]
        if move == 3:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif move == 1:
            i -= 1
        elif move == 2:
            j -= 1
        else:
            break
    return sorted(pairs)


def _fit_error_line(times: Sequence[float], errors: Sequence[float]) -> tuple[float, float] | None:
    """Least-squares line of onset error against reference time: (slope in seconds per second, error at time zero)."""
    if len(times) < 3:
        return None
    mean_t = sum(times) / len(times)
    mean_e = sum(errors) / len(errors)
    spread = sum((t - mean_t) ** 2 for t in times)
    if spread == 0:
        return None
    slope = sum((t - mean_t) * (e - mean_e) for t, e in zip(times, errors)) / spread
    return slope, mean_e - slope * mean_t


def compare_arrangements(
    reference: Sequence[DiffNote],
    generated: Sequence[DiffNote],
    *,
    trust_tier: TrustTier,
    thresholds: Thresholds = Thresholds(),
) -> CorpusDifferential:
    """Compare a generated arrangement with a reference and return aggregate metrics plus a verdict."""
    if trust_tier not in ("A", "B", "C"):
        raise ValueError("trust_tier must be 'A', 'B' or 'C'")
    ref = sorted(reference, key=lambda n: (n.onset_seconds, n.midi))
    gen = sorted(generated, key=lambda n: (n.onset_seconds, n.midi))
    authoritative = trust_tier in ("A", "B")

    if not ref:
        return _empty(trust_tier, authoritative, len(gen), "NO_REFERENCE_EVENTS")

    pairs = _align(ref, gen)
    times = [ref[i].onset_seconds for i, _j in pairs]
    errors = [gen[j].onset_seconds - ref[i].onset_seconds for i, j in pairs]
    phase: float | None
    line = _fit_error_line(times, errors)
    drift: float | None
    if line is not None:  # phase is the error at the start of the song, drift is how it grows: a pure shift has no drift
        slope, phase = line
        drift = slope * 60.0
        residuals = [abs(e - (phase + slope * t)) for t, e in zip(times, errors)]
    else:
        phase = median(errors) if errors else None
        drift = None
        residuals = [abs(e - phase) for e in errors] if phase is not None else []
    jitter: float | None = median(residuals) if residuals else None
    outliers: float | None = (
        sum(1 for r in residuals if r > thresholds.fail_phase_seconds) / len(residuals) if residuals else None
    )

    matched_ref = {i for i, _j in pairs}
    matched_gen = {j for _i, j in pairs}
    wrong = 0
    if phase is not None or not pairs:
        shift = phase or 0.0
        free_gen = [j for j in range(len(gen)) if j not in matched_gen]
        taken: set[int] = set()
        for i in range(len(ref)):
            if i in matched_ref:
                continue
            best = None
            for j in free_gen:
                if j in taken:
                    continue
                gap = abs(gen[j].onset_seconds - shift - ref[i].onset_seconds)
                if gap <= WRONG_PITCH_WINDOW_SECONDS and (best is None or gap < best[0]):
                    best = (gap, j)
            if best is not None:
                taken.add(best[1])
                wrong += 1

    matched = len(pairs)
    missed = len(ref) - matched - wrong
    extra = len(gen) - matched - wrong
    recall = matched / len(ref)
    precision = matched / len(gen) if gen else 0.0
    pitch_agreement = matched / (matched + wrong) if (matched + wrong) else 0.0

    with_position = [(ref[i], gen[j]) for i, j in pairs if None not in (ref[i].string, ref[i].fret, gen[j].string, gen[j].fret)]
    string_fret = (
        sum(1 for r, g in with_position if (r.string, r.fret) == (g.string, g.fret)) / len(with_position)
        if with_position
        else None
    )
    with_duration = [(ref[i], gen[j]) for i, j in pairs if ref[i].duration_seconds > 0]
    duration_agreement = (
        sum(min(r.duration_seconds, g.duration_seconds) / max(r.duration_seconds, g.duration_seconds, 1e-9) for r, g in with_duration)
        / len(with_duration)
        if with_duration
        else None
    )
    first_phase = gen[0].onset_seconds - ref[0].onset_seconds if gen else None

    reasons: list[str] = []
    verdict = _verdict(thresholds, phase, first_phase, drift, jitter, outliers, recall, precision, pitch_agreement, reasons)
    if not authoritative and verdict != "REVIEW_REQUIRED":
        reasons.append("TIER_C_NOT_AUTHORITATIVE")
        verdict = "REVIEW_REQUIRED"
    return CorpusDifferential(
        trust_tier=trust_tier,
        authoritative=authoritative,
        verdict=verdict,
        reasons=tuple(reasons),
        reference_notes=len(ref),
        generated_notes=len(gen),
        matched_notes=matched,
        wrong_pitch_notes=wrong,
        missed_notes=missed,
        extra_notes=extra,
        first_event_phase_seconds=_r(first_phase),
        onset_phase_seconds=_r(phase),
        onset_drift_seconds_per_minute=_r(drift),
        onset_jitter_seconds=_r(jitter),
        onset_outlier_fraction=_r(outliers),
        recall=round(recall, 6),
        precision=round(precision, 6),
        pitch_agreement=round(pitch_agreement, 6),
        string_fret_agreement=_r(string_fret),
        duration_agreement=_r(duration_agreement),
    )


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _verdict(t: Thresholds, phase: float | None, first_phase: float | None, drift: float | None,
             jitter: float | None, outliers: float | None, recall: float, precision: float,
             pitch_agreement: float, reasons: list[str]) -> Verdict:
    failed = False
    if phase is None:
        reasons.append("NO_MATCHED_NOTES")
        failed = True
    elif abs(phase) > t.fail_phase_seconds:
        reasons.append("TIMING_PHASE_ERROR")
        failed = True
    if drift is not None and abs(drift) > t.fail_drift_seconds_per_minute:
        reasons.append("TEMPO_DRIFT")
        failed = True
    if jitter is not None and jitter > t.fail_jitter_seconds:
        reasons.append("TIMING_JITTER")
        failed = True
    if outliers is not None and outliers > t.fail_outlier_fraction:
        reasons.append("MISTIMED_NOTES")
        failed = True
    if recall < t.fail_recall:
        reasons.append("MISSING_NOTES")
        failed = True
    if pitch_agreement < t.fail_pitch_agreement:
        reasons.append("WRONG_NOTES")
        failed = True
    if failed:
        return "FAIL"
    competing = (
        phase is not None and first_phase is not None and abs(first_phase - phase) > t.fail_phase_seconds
    )
    if competing:  # the song start and the fitted clock disagree: another alignment could be hiding a displacement
        reasons.append("COMPETING_ALIGNMENT")
    clean = (
        not competing
        and phase is not None and abs(phase) <= t.pass_phase_seconds
        and (drift is None or abs(drift) <= t.pass_drift_seconds_per_minute)
        and (jitter is None or jitter <= t.pass_jitter_seconds)
        and (outliers is None or outliers <= t.pass_outlier_fraction)
        and recall >= t.pass_recall and precision >= t.pass_precision and pitch_agreement >= t.pass_pitch_agreement
    )
    if clean:
        return "PASS"
    if not competing:
        reasons.append("WITHIN_FAIL_LIMITS_BUT_NOT_CLEAN")
    return "REVIEW_REQUIRED"


def _empty(trust_tier: TrustTier, authoritative: bool, generated: int, reason: str) -> CorpusDifferential:
    return CorpusDifferential(
        trust_tier=trust_tier, authoritative=authoritative, verdict="REVIEW_REQUIRED", reasons=(reason,),
        reference_notes=0, generated_notes=generated, matched_notes=0, wrong_pitch_notes=0, missed_notes=0,
        extra_notes=generated, first_event_phase_seconds=None, onset_phase_seconds=None,
        onset_drift_seconds_per_minute=None, onset_jitter_seconds=None, onset_outlier_fraction=None, recall=0.0,
        precision=0.0, pitch_agreement=0.0, string_fret_agreement=None, duration_agreement=None,
    )


def mutate_timing_phase(notes: Sequence[DiffNote], shift_seconds: float) -> list[DiffNote]:
    """A deliberately wrong copy: every onset shifted by ``shift_seconds`` (clamped at zero)."""
    return [replace(n, onset_seconds=max(0.0, n.onset_seconds + shift_seconds)) for n in notes]


def mutate_pitch(notes: Sequence[DiffNote], indices: Sequence[int], semitones: int = 1) -> list[DiffNote]:
    """A deliberately wrong copy: the notes at ``indices`` moved by ``semitones`` (string/fret left stale on purpose)."""
    wanted = set(indices)
    return [replace(n, midi=n.midi + semitones) if k in wanted else n for k, n in enumerate(notes)]
