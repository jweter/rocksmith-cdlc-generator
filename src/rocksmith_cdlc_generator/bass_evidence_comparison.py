"""Private, bounded known-truth Bass source A/B comparison.

Uses the existing authoritative synthetic fixture and BenchmarkChart scorer.
Does not run a separator, download models, publish private audio or change
the authoritative Rocksmith chart. Explicit --execute is required for pYIN.
"""
from __future__ import annotations

from collections.abc import Callable
import json
import math
from pathlib import Path
import shutil
import time
import wave

from .auto_cdlc_readiness import available_memory_gib
from .auto_cdlc_truth import verify_known_truth
from .benchmark import BenchmarkChart, BenchmarkNote, evaluate_chart
from .benchmark_adapters import from_bass_transcription
from .corpus_differential_harness import refuse_output_inside_repository_checkout
from .hashing import sha256_file
from .stems import StemSeparationError, verified_project_stem
from .stem_content_alignment import audit_stem_content_alignment
from .transcription import BassTranscription

COMPARISON_VERSION = "original-focused-stem-v1"
MIN_AVAILABLE_RAM_GIB = 4.0
MIN_FREE_DISK_GIB = 2.0
MAX_WAV_SECONDS = 45.0
MAX_SOURCE_BYTES = 30 * 1024 * 1024


class BassEvidenceBenchmarkError(ValueError):
    pass


def _geometry(path: Path) -> tuple[int, int, int, int]:
    try:
        with wave.open(str(path), "rb") as reader:
            if reader.getcomptype() != "NONE" or reader.getsampwidth() != 2:
                raise BassEvidenceBenchmarkError("PCM16_REQUIRED")
            sample_rate, channels, frames = (
                reader.getframerate(), reader.getnchannels(), reader.getnframes()
            )
        if sample_rate <= 0 or channels not in (1, 2) or frames <= 0:
            raise BassEvidenceBenchmarkError("INVALID_AUDIO_GEOMETRY")
        if frames / sample_rate > MAX_WAV_SECONDS or path.stat().st_size > MAX_SOURCE_BYTES:
            raise BassEvidenceBenchmarkError("AUDIO_EXCEEDS_BOUNDED_FIXTURE")
        return sample_rate, channels, frames, 2
    except (wave.Error, EOFError, OSError) as exc:
        raise BassEvidenceBenchmarkError("UNREADABLE_PCM") from exc


def _focused_source(project: Path, specified: Path | None, source_hash: str) -> tuple[Path | None, str]:
    if specified is None:
        return None, "FOCUSED_ARTIFACT_NOT_SPECIFIED"
    focused = Path(specified).resolve()
    expected_dir = (project / "audio" / "derived" / "instrument_focus").resolve()
    if focused.parent != expected_dir or focused.suffix.lower() != ".wav" or not focused.is_file():
        return None, "FOCUSED_PATH_NOT_LOCAL_DERIVED_AUDIO"
    metadata = focused.with_suffix(".json")
    if not metadata.is_file():
        return None, "FOCUSED_RECEIPT_MISSING"
    try:
        receipt = json.loads(metadata.read_text(encoding="utf-8"))
        params = receipt["parameters"]
        if (
            not isinstance(params, dict)
            or params.get("role") != "bass"
            or not isinstance(params.get("tuning_midi"), list)
            or len(params["tuning_midi"]) not in (4, 5, 6)
            or params.get("source_sha256") != source_hash
            or receipt.get("output_sha256") != sha256_file(focused)
        ):
            return None, "FOCUSED_RECEIPT_MISMATCH"
    except (OSError, ValueError, TypeError, KeyError):
        return None, "FOCUSED_RECEIPT_INVALID"
    return focused, "REGISTER_FOCUS_ONLY_NOT_ISOLATION"


def _original_truth_chart(truth: dict) -> BenchmarkChart:
    return BenchmarkChart(
        case_id="original-clock-bass-source-comparison",
        arrangement="bass",
        audio_duration_seconds=float(truth["duration_seconds"]),
        notes=[
            BenchmarkNote(
                start_seconds=float(note["onset_seconds"]),
                duration_seconds=float(note["duration_seconds"]),
                midi=int(note["midi"]),
            )
            for note in truth["bass_notes"]
        ],
    )


def _default_transcribe(path: Path) -> BassTranscription:
    # Import only after explicit execution and preflight. This does not invoke
    # the external separator/model or touch the global project transcription.
    from .librosa_transcription import LibrosaPyinBassTranscriber
    return LibrosaPyinBassTranscriber().transcribe(path)


def compare_bass_evidence_sources(
    fixture_dir: Path,
    project_dir: Path,
    out_path: Path,
    *,
    focused_path: Path | None = None,
    execute: bool = False,
    memory_probe: Callable[[], float] = available_memory_gib,
    transcriber: Callable[[Path], BassTranscription] | None = None,
) -> dict:
    """Score prepared local audio, never construct new models or alter charts.

    The source WAV must be *identical* to the verified generated original;
    a different recording/song can never use that ground truth. A missing
    focused or stem source is classified, not invented.
    """
    fixture_dir, project_dir, out_path = (
        Path(fixture_dir).resolve(), Path(project_dir).resolve(), Path(out_path).resolve()
    )
    refuse_output_inside_repository_checkout(out_path)
    # This program owns exactly one generated report filename. Caller-supplied
    # --out is NOT permission to replace the normalized recording, a stem,
    # its hash receipts, bass_raw.json, a score or other project authority.
    # Resolve symlinks before comparing to reject indirect overwrite attacks.
    if (
        not out_path.is_relative_to(project_dir)
        or out_path.parent != (project_dir / "analysis").resolve()
        or out_path.name != "bass-source-comparison.json"
    ):
        raise BassEvidenceBenchmarkError("OUTPUT_MUST_BE_DEDICATED_BASS_COMPARISON_REPORT")
    original, truth = verify_known_truth(fixture_dir)
    original_hash = sha256_file(original)
    source = (project_dir / "audio" / "normalized.wav").resolve()
    if not source.is_relative_to(project_dir) or not source.is_file() or sha256_file(source) != original_hash:
        raise BassEvidenceBenchmarkError("PROJECT_SOURCE_DIFFERS_FROM_KNOWN_TRUTH")
    geometry = _geometry(source)
    if geometry[0] != truth["sample_rate_hz"] or abs(geometry[2] / geometry[0] - truth["duration_seconds"]) > 0.00001:
        raise BassEvidenceBenchmarkError("PROJECT_GEOMETRY_DIFFERS_FROM_KNOWN_TRUTH")

    sources: dict[str, tuple[Path | None, str]] = {
        "original": (source, "FULL_MIX_NOT_INSTRUMENT_ISOLATION")
    }
    focused, focus_reason = _focused_source(project_dir, focused_path, original_hash)
    sources["focused"] = (focused, focus_reason)
    try:
        bass = verified_project_stem(project_dir, "bass")
        clock = audit_stem_content_alignment(source, bass)
        sources["stem"] = (bass, "STEM_CLOCK_" + clock.status.upper())
    except (StemSeparationError, OSError, ValueError):
        sources["stem"] = (None, "VERIFIED_STEM_UNAVAILABLE")

    results: dict[str, dict] = {}
    ready: dict[str, Path] = {}
    for mode, (path, source_reason) in sources.items():
        record = {"source_type": mode, "status": "UNAVAILABLE", "reason": source_reason,
                  "input_sha256": None, "qualified_f1": None, "raw_note_f1": None,
                  "onset_mae_seconds": None, "false_positive_count": None,
                  "review_required_count": None, "elapsed_seconds": None,
                  "peak_process_ram_gib": None}
        if path is not None:
            try:
                candidate_geometry = _geometry(path)
                if candidate_geometry != geometry:
                    record["reason"] = "SOURCE_PCM_CLOCK_MISMATCH"
                else:
                    record["input_sha256"] = sha256_file(path)
                    if mode == "stem" and source_reason != "STEM_CLOCK_ALIGNED":
                        # Keep its hash and timing diagnostics, but don't call
                        # misaligned/ambiguous audio a ready instrument oracle.
                        record["status"] = "UNQUALIFIED_CLOCK"
                    else:
                        record["status"] = "READY"
                        ready[mode] = path
            except BassEvidenceBenchmarkError as exc:
                record["reason"] = str(exc)
        results[mode] = record

    preflight = {
        "operator_opt_in": bool(execute),
        "status": "READINESS_ONLY",
        "available_ram_gib": None,
        "free_disk_gib": None,
        "minimum_available_ram_gib": MIN_AVAILABLE_RAM_GIB,
        "minimum_free_disk_gib": MIN_FREE_DISK_GIB,
    }
    if execute:
        # No fallback to swap/installed capacity; cannot load a CPU-heavy
        # transcriber without this admission proof.
        try:
            free_ram = memory_probe()
            free_disk = shutil.disk_usage(out_path.parent if out_path.parent.exists() else project_dir).free / (1024 ** 3)
            if not math.isfinite(free_ram) or free_ram < 0:
                raise ValueError("RAM_PROBE_INVALID")
            preflight.update(available_ram_gib=round(free_ram, 3), free_disk_gib=round(free_disk, 3))
        except (OSError, ValueError):
            preflight["status"] = "BLOCKED_RESOURCE_PROBE"
        else:
            preflight["status"] = (
                "ADMITTED" if free_ram >= MIN_AVAILABLE_RAM_GIB and free_disk >= MIN_FREE_DISK_GIB
                else "BLOCKED_RESOURCES"
            )
    if execute and preflight["status"] == "ADMITTED":
        oracle = transcriber or _default_transcribe
        reference = _original_truth_chart(truth)
        for mode, path in ready.items():
            # Other concurrent Windows workloads may consume RAM between
            # first admission and later pYIN passes. Recheck at every source.
            try:
                refreshed_ram = memory_probe()
                if not math.isfinite(refreshed_ram) or refreshed_ram < MIN_AVAILABLE_RAM_GIB:
                    results[mode].update(status="BLOCKED_RESOURCES", reason="PHYSICAL_RAM_FELL_BELOW_FLOOR")
                    continue
            except (OSError, ValueError):
                results[mode].update(status="BLOCKED_RESOURCES", reason="PHYSICAL_RAM_PROBE_FAILED")
                continue
            before = results[mode]["input_sha256"]
            start = time.monotonic()
            try:
                candidate = oracle(path)
                if sha256_file(path) != before or candidate.source_sha256 != before:
                    raise BassEvidenceBenchmarkError("TRANSCRIPTION_INPUT_HASH_UNPROVEN")
                if candidate.sample_rate_hz != geometry[0]:
                    raise BassEvidenceBenchmarkError("TRANSCRIPTION_SAMPLE_RATE_MISMATCH")
                raw_chart = from_bass_transcription(
                    candidate, case_id=reference.case_id,
                    audio_duration_seconds=reference.audio_duration_seconds,
                )
                strong = [
                    note for note in candidate.notes
                    if note.confidence >= .70 and note.pitch_confidence >= .60
                    and note.timing_confidence >= .75 and not note.review_required
                ]
                strong_chart = from_bass_transcription(
                    candidate.model_copy(update={"notes": strong}),
                    case_id=reference.case_id,
                    audio_duration_seconds=reference.audio_duration_seconds,
                )
                raw_metrics = evaluate_chart(reference, raw_chart)
                qualified_metrics = evaluate_chart(reference, strong_chart)
                results[mode].update(
                    status="SCORED_REVIEW_ONLY",
                    raw_note_f1=round(raw_metrics.note_f1, 6),
                    qualified_f1=round(qualified_metrics.note_f1, 6),
                    onset_mae_seconds=qualified_metrics.onset_mae_seconds,
                    false_positive_count=qualified_metrics.false_positive_count,
                    review_required_count=raw_metrics.review_required_count,
                    raw_note_count=len(candidate.notes),
                    strong_note_count=len(strong),
                )
            except BassEvidenceBenchmarkError as exc:
                results[mode].update(status="UNQUALIFIED", reason=str(exc)[:110])
            except (OSError, ValueError, wave.Error, EOFError):
                # Do not publish exception messages; they may contain private
                # absolute paths, media filenames or source data.
                results[mode].update(status="UNQUALIFIED", reason="ANALYZER_INPUT_FAILURE")
            except (RuntimeError, ImportError):
                results[mode].update(status="UNQUALIFIED", reason="LOCAL_TRANSCRIBER_UNAVAILABLE")
            finally:
                results[mode]["elapsed_seconds"] = round(time.monotonic() - start, 3)
    verdict = "READINESS_ONLY" if not execute else (
        "COMPARISON_SCORED" if preflight["status"] == "ADMITTED" and any(
            row["status"] == "SCORED_REVIEW_ONLY" for row in results.values()
        ) else "BLOCKED_OR_UNQUALIFIED"
    )
    report = {
        "schema_version": 1,
        "comparison_version": COMPARISON_VERSION,
        "scope": "VERIFIED_SYNTHETIC_ORIGINAL_CLOCK_ONLY",
        "recording_sha256": original_hash,
        "truth_note_count": len(truth["bass_notes"]),
        "source_results": results,
        "resource_preflight": preflight,
        "comparison_verdict": verdict,
        "musical_acceptance": "NOT_PROVEN",
        "gameplay_acceptance": "NOT_PROVEN",
        "source_separation_purity": "NOT_PROVEN",
    }
    # A report is never a music PASS, even when F1 looks high.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(out_path)
    return report
