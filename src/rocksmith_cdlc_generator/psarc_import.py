from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .hashing import sha256_file
from .source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
)

_STANDARD_BASS_OPEN_MIDI = (28, 33, 38, 43)
_BRIDGE_COMMIT = "b87c9a3afd31c40ade9685a9244e718e7581c0cb"
_TICKS_PER_BEAT = 480


class PsarcImportError(ValueError):
    pass


class PsarcBridgeUnavailable(RuntimeError):
    pass


def _truthy_attribute(note: ET.Element, name: str) -> bool:
    value = note.attrib.get(name)
    if value is None:
        return False
    try:
        return int(value) != 0
    except ValueError:
        return value.strip().lower() in {"true", "yes"}


def _note_techniques(note: ET.Element) -> list[str]:
    direct_flags = {
        "accent": "accent",
        "hammerOn": "hammer_on",
        "harmonic": "harmonic",
        "mute": "fret_hand_mute",
        "palmMute": "palm_mute",
        "pullOff": "pull_off",
        "tremolo": "tremolo_picking",
        "harmonicPinch": "pinch_harmonic",
        "linkNext": "link_next",
    }
    result = [label for attribute, label in direct_flags.items() if _truthy_attribute(note, attribute)]
    if note.attrib.get("slap") not in (None, "-1"):
        result.append("slap")
    if note.attrib.get("pluck") not in (None, "-1"):
        result.append("pluck")
    if note.attrib.get("tap") not in (None, "0", "-1"):
        result.append("tap")
    if note.attrib.get("vibrato") not in (None, "0"):
        result.append("vibrato")
    if note.attrib.get("bend") not in (None, "0", "0.0", "0.000") or note.find("bendValues") is not None:
        result.append("bend")
    if note.attrib.get("slideTo") not in (None, "-1"):
        result.append("slide")
    if note.attrib.get("slideUnpitchTo") not in (None, "-1"):
        result.append("unpitched_slide")
    return sorted(set(result))


def _tuning_from_xml(root: ET.Element) -> list[int]:
    tuning = root.find("tuning")
    if tuning is None:
        raise PsarcImportError("Rocksmith Bass XML does not contain a tuning element")
    result: list[int] = []
    for index, standard in enumerate(_STANDARD_BASS_OPEN_MIDI):
        try:
            offset = int(tuning.attrib.get(f"string{index}", "0"))
        except ValueError as exc:
            raise PsarcImportError(f"Invalid Rocksmith tuning offset for string {index}") from exc
        result.append(standard + offset)
    return result


def _beat_grid(root: ET.Element) -> list[float]:
    beat_times: list[float] = []
    for beat in root.findall("ebeats/ebeat"):
        try:
            time = float(beat.attrib["time"])
        except (KeyError, ValueError) as exc:
            raise PsarcImportError("Rocksmith XML contains an invalid ebeat time") from exc
        if time < 0:
            raise PsarcImportError("Rocksmith XML contains a negative ebeat time")
        if beat_times and time <= beat_times[-1] + 1e-6:
            raise PsarcImportError("Rocksmith XML ebeat times must be strictly increasing")
        beat_times.append(time)
    if len(beat_times) < 2:
        raise PsarcImportError("Rocksmith Bass XML needs at least two ebeats")
    return beat_times


def _tempo_events(beat_times: list[float]) -> list[SourceTempoEvent]:
    events: list[SourceTempoEvent] = []
    previous_bpm: float | None = None
    for index, (left, right) in enumerate(zip(beat_times, beat_times[1:])):
        interval = right - left
        bpm = 60.0 / interval
        if previous_bpm is None:
            events.append(SourceTempoEvent(tick=0, time_seconds=0.0, bpm=bpm))
        elif abs(bpm - previous_bpm) > 0.05:
            events.append(SourceTempoEvent(tick=index * _TICKS_PER_BEAT, time_seconds=left, bpm=bpm))
        previous_bpm = bpm
    return events


def _time_signatures(root: ET.Element) -> list[SourceTimeSignatureEvent]:
    result: list[SourceTimeSignatureEvent] = []
    for event in root.findall("events/event"):
        code = event.attrib.get("code", "")
        if not code.upper().startswith("TS:") or "/" not in code:
            continue
        try:
            numerator_text, denominator_text = code[3:].split("/", 1)
            numerator = int(numerator_text)
            denominator = int(denominator_text)
            time = float(event.attrib.get("time", "0"))
        except ValueError:
            continue
        result.append(
            SourceTimeSignatureEvent(
                tick=0,
                time_seconds=max(0.0, time),
                numerator=numerator,
                denominator=denominator,
            )
        )
    if not result:
        result.append(SourceTimeSignatureEvent(tick=0, time_seconds=0.0, numerator=4, denominator=4))
    return result


def _full_difficulty_notes(root: ET.Element) -> tuple[list[ET.Element], int, int]:
    levels = root.findall("levels/level")
    if not levels:
        raise PsarcImportError("Rocksmith Bass XML contains no difficulty levels")
    ranked: list[tuple[int, ET.Element]] = []
    for level in levels:
        try:
            difficulty = int(level.attrib.get("difficulty", "0"))
        except ValueError:
            difficulty = 0
        ranked.append((difficulty, level))
    difficulty, selected = max(ranked, key=lambda item: item[0])
    notes = selected.findall("notes/note")
    chord_count = len(selected.findall("chords/chord"))
    return notes, chord_count, difficulty


def convert_rocksmith_bass_xml(
    xml_path: Path,
    *,
    source_path: Path,
    source_sha256: str,
    importer_version: str = _BRIDGE_COMMIT,
) -> ImportedSource:
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise PsarcImportError(f"Could not parse extracted Rocksmith Bass XML: {xml_path}") from exc

    arrangement = (root.findtext("arrangement") or "").strip().lower()
    if arrangement != "bass":
        raise PsarcImportError(f"Expected a Bass arrangement, found {arrangement or '<unknown>'}")

    tuning = _tuning_from_xml(root)
    beat_times = _beat_grid(root)
    xml_notes, chord_count, difficulty = _full_difficulty_notes(root)
    warnings: list[str] = []
    if chord_count:
        warnings.append(
            f"Rocksmith Bass arrangement contains {chord_count} chord event(s); chord/double-stop reconstruction is not yet imported."
        )

    notes: list[SourceNoteEvent] = []
    for note in xml_notes:
        try:
            start = float(note.attrib["time"])
            string_index = int(note.attrib["string"])
            fret = int(note.attrib["fret"])
            duration = float(note.attrib.get("sustain", "0"))
        except (KeyError, ValueError) as exc:
            raise PsarcImportError("Rocksmith Bass XML contains an invalid note") from exc
        if not 0 <= string_index < 4:
            warnings.append(f"Skipped note at {start:.3f}s on unsupported Bass string {string_index}.")
            continue
        if fret < 0:
            warnings.append(f"Skipped note at {start:.3f}s with negative fret {fret}.")
            continue
        midi = tuning[string_index] + fret
        techniques = _note_techniques(note)
        notes.append(
            SourceNoteEvent(
                start_seconds=max(0.0, start),
                duration_seconds=max(0.001, duration),
                midi=midi,
                string_index=string_index,
                fret=fret,
                techniques=techniques,
                import_confidence=1.0,
                review_required=False,
            )
        )
    notes.sort(key=lambda item: (item.start_seconds, item.string_index or 0, item.midi))
    if not notes:
        raise PsarcImportError("Extracted Rocksmith Bass arrangement contains no importable single notes")

    warnings.append(
        f"Imported highest Rocksmith difficulty level {difficulty}; source remains symbolic_unverified until reconciled against audio."
    )
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="rocksmith_psarc",
            source_filename=source_path.name,
            source_sha256=source_sha256,
            importer="rocksmith2014.net-psarc-bridge+xml",
            importer_version=importer_version,
        ),
        ticks_per_beat=_TICKS_PER_BEAT,
        tempo_events=_tempo_events(beat_times),
        time_signatures=_time_signatures(root),
        beat_times_seconds=beat_times,
        tracks=[
            SourceTrack(
                source_track_index=0,
                name="Bass",
                instrument="bass",
                tuning_midi=tuning,
                notes=notes,
            )
        ],
        warnings=warnings,
    )


def _default_bridge_path() -> Path:
    configured = os.environ.get("ROCKSMITH_PSARC_BRIDGE")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.cwd() / "tools" / "psarc_bridge" / "bin" / "Release" / "net10.0" / "RocksmithPsarcBridge.dll").resolve()


def _bridge_command(bridge_path: Path, psarc_path: Path, extraction_dir: Path) -> list[str]:
    if not bridge_path.is_file():
        raise PsarcBridgeUnavailable(
            f"PSARC bridge not found: {bridge_path}. Run scripts/bootstrap_psarc_bridge.ps1 first or pass --bridge."
        )
    if bridge_path.suffix.lower() == ".dll":
        dotnet = shutil.which("dotnet")
        if dotnet is None:
            raise PsarcBridgeUnavailable("The PSARC bridge requires .NET 10; dotnet was not found on PATH.")
        return [dotnet, str(bridge_path), str(psarc_path), str(extraction_dir)]
    return [str(bridge_path), str(psarc_path), str(extraction_dir)]


def import_project_psarc(project_dir: Path, psarc_path: Path, *, bridge_path: Path | None = None) -> Path:
    project_dir = project_dir.resolve()
    psarc_path = psarc_path.resolve()
    if not psarc_path.is_file():
        raise FileNotFoundError(psarc_path)
    if psarc_path.suffix.lower() != ".psarc":
        raise PsarcImportError("Rocksmith package import requires a .psarc file")
    with psarc_path.open("rb") as handle:
        if handle.read(4) != b"PSAR":
            raise PsarcImportError("Selected file does not have a PSARC header")

    source_sha = sha256_file(psarc_path)
    bridge = bridge_path.resolve() if bridge_path is not None else _default_bridge_path()
    with tempfile.TemporaryDirectory(prefix="rocksmith-psarc-") as temp:
        extraction_dir = Path(temp)
        command = _bridge_command(bridge, psarc_path, extraction_dir)
        try:
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "PSARC bridge failed").strip()
            raise PsarcImportError(detail) from exc
        try:
            bridge_result = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as exc:
            raise PsarcImportError("PSARC bridge returned invalid JSON") from exc

        candidates = [Path(path) for path in bridge_result.get("bassXmlPaths", [])]
        if not candidates:
            candidates = [path for path in extraction_dir.glob("arr_*_RS2.xml") if "bass" in path.stem.lower()]
        if len(candidates) != 1:
            raise PsarcImportError(
                f"Expected exactly one Bass arrangement in selected PSARC, found {len(candidates)}. Song packs/ambiguous Bass packages are not imported."
            )
        xml_path = candidates[0]
        if not xml_path.is_absolute():
            xml_path = extraction_dir / xml_path
        imported = convert_rocksmith_bass_xml(
            xml_path,
            source_path=psarc_path,
            source_sha256=source_sha,
            importer_version=str(bridge_result.get("upstreamCommit") or _BRIDGE_COMMIT),
        )

    destination = project_dir / "sources" / "imported" / f"{psarc_path.stem}-{source_sha[:12]}.json"
    return imported.write_json(destination)
