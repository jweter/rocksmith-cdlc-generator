"""Untrusted auto-cdlc output as an independent, non-authoritative timing oracle.

This adapter consumes upstream .mid (original recording clock), .svl (COUNT
bar + padded recording clock) and diagnostico.json (contains silence padding).
It never imports upstream model code, invokes its updater or promotes a chart.
All private note events remain local: returned reports contain only aggregates.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
import tempfile
from math import isfinite
from pathlib import Path
import re
from statistics import median
from xml.etree import ElementTree as ET

import mido

from .beats import read_tempo_map
from .build_identity import current_build_identity
from .corpus_differential import DiffNote, compare_arrangements
from .corpus_differential_harness import refuse_output_inside_repository_checkout
from .hashing import sha256_file
from .models import ProjectManifest
from .transcription import read_transcription

_MAX_INPUT_BYTES = 16 * 1024 * 1024
_MAX_NOTES = 3500
_MAX_BEATS = 20000
_SVL_DOCTYPE = "<!DOCTYPE sonic-visualiser>"
_UPSTREAM = "fesaje/auto-cdlc"
_REVIEWED_COMMIT = "cd7826f6a05a9acf8ff1825d52af9e2656d27d01"


class AutoCdlcOracleError(ValueError):
    """An upstream export or project input is missing, ambiguous or malformed."""


def _one_export(directory: Path, suffix: str) -> Path:
    candidates = sorted(path for path in directory.glob("*" + suffix) if path.is_file())
    if len(candidates) != 1:
        raise AutoCdlcOracleError(
            f"Upstream export must contain exactly one {suffix} file; found {len(candidates)}"
        )
    if candidates[0].stat().st_size > _MAX_INPUT_BYTES:
        raise AutoCdlcOracleError(f"Upstream {suffix} export exceeds {_MAX_INPUT_BYTES} bytes")
    return candidates[0]


def _diagnostic(path: Path) -> tuple[float, str | None]:
    if not path.is_file() or path.stat().st_size > _MAX_INPUT_BYTES:
        raise AutoCdlcOracleError("Missing or oversized upstream diagnostico.json")
    try:
        diagnostic = json.loads(path.read_text(encoding="utf-8"))
        padding = float(diagnostic["resultado"]["silencio_inicial_s"])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise AutoCdlcOracleError(
            "Upstream diagnostico.json must contain resultado.silencio_inicial_s"
        ) from exc
    if not isfinite(padding) or padding < 0:
        raise AutoCdlcOracleError("Upstream added-silence offset must be finite and nonnegative")
    version = diagnostic.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9][0-9A-Za-z._+-]{0,30}", version):
        version = None
    return padding, version


def read_upstream_svl(path: Path, *, padding_seconds: float) -> tuple[list[float], list[float]]:
    """Convert SVL's padded four-beat COUNT clock back to original recording time.

    The inspected upstream 'escribir_svl' writes four count-in points before
    the extended audio beat grid and adds 'silencio_inicial_s' to *all* points.
    The separate upstream MIDI output is already on the original audio clock.
    """
    if path.stat().st_size > _MAX_INPUT_BYTES:
        raise AutoCdlcOracleError("SVL is too large")
    text = path.read_text(encoding="utf-8")
    if "<!ENTITY" in text or ("<!DOCTYPE" in text and _SVL_DOCTYPE not in text):
        raise AutoCdlcOracleError("Unexpected XML declaration/entity in upstream SVL")
    text = text.replace(_SVL_DOCTYPE, "")
    if "<!DOCTYPE" in text:
        raise AutoCdlcOracleError("Multiple or unexpected DOCTYPE declarations in SVL")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise AutoCdlcOracleError("Invalid upstream SVL XML") from exc
    if root.tag != "sv":
        raise AutoCdlcOracleError("SVL root must be <sv>")
    models = root.findall("./data/model")
    if len(models) != 1 or models[0].get("name") != "Beats":
        raise AutoCdlcOracleError("Expected exactly one upstream Beats model")
    model = models[0]
    try:
        sample_rate = int(model.attrib["sampleRate"])
        dataset_id = model.attrib["dataset"]
    except (ValueError, KeyError) as exc:
        raise AutoCdlcOracleError("SVL model lacks sample rate or dataset identifier") from exc
    if sample_rate != 44100:
        raise AutoCdlcOracleError("Unexpected SVL sample rate; upstream format requires 44100 Hz")
    datasets = root.findall("./data/dataset")
    if len(datasets) != 1 or datasets[0].get("id") != dataset_id:
        raise AutoCdlcOracleError("SVL Beats dataset is ambiguous or missing")
    rows: list[tuple[float, int]] = []
    try:
        for point in datasets[0].findall("point"):
            frame = int(point.attrib["frame"])
            label = int(point.attrib["label"])
            if frame < 0 or not 1 <= label <= 6:
                raise ValueError("invalid frame or beat label")
            rows.append((frame / sample_rate, label))
    except (ValueError, KeyError) as exc:
        raise AutoCdlcOracleError("SVL contains an invalid beat point") from exc
    if len(rows) < 6 or len(rows) > _MAX_BEATS:
        raise AutoCdlcOracleError("SVL must contain count-in plus at least two audio beats")
    if [label for _time, label in rows[:4]] != [1, 2, 3, 4]:
        raise AutoCdlcOracleError("SVL four-beat COUNT pattern missing; cannot remove lead-in safely")
    if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
        raise AutoCdlcOracleError("SVL beat frames must be strictly increasing")
    # The upstream grid can extrapolate earlier than audio time zero; those
    # beats are not observed audio evidence. Never manufacture negatives or
    # globally fit the phase to make two engines appear to agree.
    measured = [(t - padding_seconds, label) for t, label in rows[4:]]
    measured = [(t, label) for t, label in measured if t >= -0.001]
    beats = [max(0.0, t) for t, _label in measured]
    downbeats = [max(0.0, t) for t, label in measured if label == 1]
    if len(beats) < 2:
        raise AutoCdlcOracleError("SVL has insufficient beats on the unpadded audio clock")
    return beats, downbeats


def read_upstream_midi(path: Path) -> list[DiffNote]:
    """Read MIDI in real seconds, honouring tempo changes and note-off semantics."""
    if path.stat().st_size > _MAX_INPUT_BYTES:
        raise AutoCdlcOracleError("Upstream MIDI exceeds size limit")
    try:
        song = mido.MidiFile(path)
        if song.type == 2:
            raise AutoCdlcOracleError("Type-2 asynchronous MIDI has no single recording clock")
        active: dict[tuple[int, int], list[float]] = {}
        results: list[DiffNote] = []
        clock = 0.0
        for message in song:  # mido's iterator merges tracks and yields seconds, not ticks
            clock += message.time
            if not isfinite(clock) or clock < 0:
                raise AutoCdlcOracleError("MIDI contains invalid absolute time")
            if message.type not in ("note_on", "note_off") or message.channel == 9:
                continue
            key = (message.channel, message.note)
            if message.type == "note_on" and message.velocity > 0:
                active.setdefault(key, []).append(clock)
            else:
                if not active.get(key):
                    raise AutoCdlcOracleError("Unmatched upstream MIDI note-off")
                start = active[key].pop(0)
                if clock <= start:
                    raise AutoCdlcOracleError("Upstream MIDI note has zero/negative duration")
                results.append(DiffNote(start, clock - start, message.note))
                if len(results) > _MAX_NOTES:
                    raise AutoCdlcOracleError("Upstream MIDI note count exceeds comparison limit")
        if any(starts for starts in active.values()):
            raise AutoCdlcOracleError("Unclosed upstream MIDI note-on event")
    except (OSError, EOFError, ValueError) as exc:
        if isinstance(exc, AutoCdlcOracleError):
            raise
        raise AutoCdlcOracleError("Cannot decode upstream MIDI") from exc
    if not results:
        raise AutoCdlcOracleError("Upstream MIDI contains no bass note events")
    return sorted(results, key=lambda note: (note.onset_seconds, note.midi))


def _beat_agreement(reference: list[float], other: list[float], *, tolerance: float = 0.07) -> dict[str, object]:
    """One-to-one absolute-clock matching: never remove a guessed global offset."""
    i = j = 0
    differences: list[float] = []
    while i < len(reference) and j < len(other):
        delta = other[j] - reference[i]
        if abs(delta) <= tolerance:
            differences.append(delta)
            i += 1
            j += 1
        elif delta < -tolerance:
            j += 1
        else:
            i += 1
    denom = len(reference) + len(other)
    return {
        "reference_count": len(reference),
        "upstream_count": len(other),
        "matched_count": len(differences),
        "f1": round(2 * len(differences) / denom, 5) if denom else None,
        "median_abs_error_seconds": round(median(map(abs, differences)), 6) if differences else None,
    }


def _validate_report_destination(
    destination: Path, *, project: Path, upstream: Path, protected_inputs: list[Path]
) -> None:
    """Prevent destructive output aliasing and overwrites of unrelated files.

    Reports may live in the project's review directory, or a separate local
    path. Never target the source/analysis/build directories, the upstream
    export directory, any direct input (including symlinks), or any preexisting
    non-report file. Re-running over our own previous report is allowed.
    """
    if destination.is_relative_to(upstream):
        raise AutoCdlcOracleError("Report destination must not overwrite upstream export data")
    if destination.is_relative_to(project) and not destination.is_relative_to(project / "review"):
        raise AutoCdlcOracleError("Report inside project must be under its review directory")
    if any(destination == item.resolve() for item in protected_inputs):
        raise AutoCdlcOracleError("Report destination overlaps a comparison input")
    if destination.exists():
        if not destination.is_file() or destination.stat().st_size > _MAX_INPUT_BYTES:
            raise AutoCdlcOracleError("Report destination already exists and is not a recognized report")
        try:
            previous = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise AutoCdlcOracleError("Refusing to replace preexisting non-report content") from exc
        if not isinstance(previous, dict) or (
            previous.get("schema_version") != 1
            or previous.get("source") != _UPSTREAM
            or previous.get("lane") != "secondary_unverified_audio_oracle"
            or previous.get("verdict") != "REVIEW_REQUIRED"
        ):
            raise AutoCdlcOracleError("Refusing to replace preexisting non-report content")


def compare_auto_cdlc_export(
    project_dir: Path, upstream_dir: Path, *, upstream_audio: Path, out_path: Path
) -> dict[str, object]:
    """Compare on one *claimed* original recording and write only local aggregates.

    Output is never authoritative: upstream diagnostics don't cryptographically
    bind its .mid/.svl to a source hash. A matching caller-supplied source file
    is necessary, not sufficient, evidence that both engines saw the same mix.
    """
    refuse_output_inside_repository_checkout(out_path)
    project = project_dir.expanduser().resolve()
    upstream = upstream_dir.expanduser().resolve()
    manifest = ProjectManifest.load(project)
    source_rel = Path(manifest.source_project_path)
    source_path = (project / source_rel).resolve()
    if source_rel.is_absolute() or not source_path.is_relative_to(project) or not source_path.is_file():
        raise AutoCdlcOracleError("Project source copy is missing or outside project boundary")
    original_hash = sha256_file(source_path)
    if original_hash != manifest.source_sha256:
        raise AutoCdlcOracleError("Project original audio hash changed")
    if sha256_file(upstream_audio.expanduser().resolve()) != original_hash:
        raise AutoCdlcOracleError("Upstream source audio must match immutable project source SHA-256")

    upstream_mid = _one_export(upstream, ".mid")
    upstream_svl = _one_export(upstream, ".svl")
    upstream_diagnostic = upstream / "diagnostico.json"
    output = out_path.expanduser().resolve()
    _validate_report_destination(
        output, project=project, upstream=upstream,
        protected_inputs=[
            source_path,
            upstream_audio.expanduser().resolve(),
            upstream_mid,
            upstream_svl,
            upstream_diagnostic,
            project / "project.json",
            project / "analysis" / "bass_raw.json",
            project / "analysis" / "tempo_map.json",
        ],
    )
    padding, version = _diagnostic(upstream_diagnostic)
    upstream_notes = read_upstream_midi(upstream_mid)
    upstream_beats, upstream_downbeats = read_upstream_svl(upstream_svl, padding_seconds=padding)

    our_notes_model = read_transcription(project / "analysis" / "bass_raw.json")
    our_tempo = read_tempo_map(project / "analysis" / "tempo_map.json")
    if not our_tempo.beats or not our_notes_model.notes:
        raise AutoCdlcOracleError("Local project lacks Bass notes or beat evidence")
    if len(our_notes_model.notes) > _MAX_NOTES:
        raise AutoCdlcOracleError("Local Bass notes exceed comparison limit")
    ours = [DiffNote(note.start, note.duration, note.midi) for note in our_notes_model.notes]
    # Tier C can only inform diagnostics: it must never become musical authority.
    diff = compare_arrangements(upstream_notes, ours, trust_tier="C")
    beat_comparison = _beat_agreement(
        [beat.time for beat in our_tempo.beats], upstream_beats
    )
    downbeat_comparison = _beat_agreement(
        [beat.time for beat in our_tempo.beats if beat.is_downbeat], upstream_downbeats
    )

    alerts: list[str] = []
    first = diff.first_event_phase_seconds
    if first is not None and abs(first) > 0.12:
        alerts.append("FIRST_BASS_ONSET_CLOCK_DISAGREEMENT")
    if diff.onset_drift_seconds_per_minute is not None and abs(diff.onset_drift_seconds_per_minute) > 0.05:
        alerts.append("BASS_DRIFT_DISAGREEMENT")
    if diff.pitch_agreement < 0.95:
        alerts.append("BASS_MIDI_PITCH_OR_OCTAVE_DISAGREEMENT")
    if beat_comparison["f1"] is not None and beat_comparison["f1"] < 0.90:
        alerts.append("BEAT_GRID_DISAGREEMENT")
    if downbeat_comparison["f1"] is not None and downbeat_comparison["f1"] < 0.80:
        alerts.append("DOWNBEAT_GRID_DISAGREEMENT")

    # No names, source paths, event arrays, timeline landmarks or lyrics.
    report: dict[str, object] = {
        "schema_version": 1,
        "source": _UPSTREAM,
        "reviewed_source_commit": _REVIEWED_COMMIT,
        "reported_upstream_version": version,
        "lane": "secondary_unverified_audio_oracle",
        "verdict": "REVIEW_REQUIRED",
        "reference_authority": "NONE",
        "source_binding": "caller_audio_hash_matches_project; upstream_export_identity_unproven",
        "input_sha256": {
            "original_audio": original_hash,
            "upstream_midi": sha256_file(upstream_mid),
            "upstream_svl": sha256_file(upstream_svl),
            "upstream_diagnostic": sha256_file(upstream_diagnostic),
            "local_bass_raw": sha256_file(project / "analysis" / "bass_raw.json"),
            "local_tempo_map": sha256_file(project / "analysis" / "tempo_map.json"),
        },
        "beat_grid": beat_comparison,
        "downbeat_grid": downbeat_comparison,
        "bass_notes": diff.sanitized(),
        "alerts": alerts,
        "build_identity": asdict(current_build_identity()),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish complete report atomically. An interrupted write must not damage
    # a previous good diagnostic or leave a truncated target.
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=".auto-cdlc-oracle-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return report
