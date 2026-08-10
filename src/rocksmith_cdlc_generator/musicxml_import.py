from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from .hashing import sha256_file
from .source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
    SourceTrustClass,
)

TICKS_PER_QUARTER = 960
IMPORTER_VERSION = "2"
ArrangementKind = Literal["bass", "lead", "rhythm"]


@dataclass
class _RawNote:
    start_q: float
    duration_q: float
    midi: int
    note_name: str
    string_index: int | None
    fret: int | None
    techniques: list[str]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    return next((child for child in parent if _local(child.tag) == name), None)


def _children(parent: ET.Element | None, name: str) -> list[ET.Element]:
    if parent is None:
        return []
    return [child for child in parent if _local(child.tag) == name]


def _text(parent: ET.Element | None, name: str, default: str | None = None) -> str | None:
    node = _child(parent, name)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def _load_root(path: Path) -> ET.Element:
    suffix = path.suffix.lower()
    if suffix == ".mxl":
        with ZipFile(path) as archive:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next((node for node in container.iter() if _local(node.tag) == "rootfile"), None)
            if rootfile is None or not rootfile.attrib.get("full-path"):
                raise ValueError("Compressed MusicXML has no rootfile entry")
            return ET.fromstring(archive.read(rootfile.attrib["full-path"]))
    return ET.parse(path).getroot()


def _pitch_to_midi(note: ET.Element) -> tuple[int, str]:
    pitch = _child(note, "pitch")
    if pitch is None:
        raise ValueError("MusicXML pitched note has no <pitch>")
    step = _text(pitch, "step")
    octave_text = _text(pitch, "octave")
    if step is None or octave_text is None:
        raise ValueError("MusicXML pitch is missing step or octave")
    alter = int(float(_text(pitch, "alter", "0") or "0"))
    semitone = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step]
    octave = int(octave_text)
    midi = 12 * (octave + 1) + semitone + alter
    accidental = "#" * alter if alter > 0 else "b" * (-alter)
    return midi, f"{step}{accidental}{octave}"


def _staff_tuning(part: ET.Element) -> list[int] | None:
    tunings: dict[int, int] = {}
    for staff_tuning in (node for node in part.iter() if _local(node.tag) == "staff-tuning"):
        line = int(staff_tuning.attrib.get("line", "0") or 0)
        step = _text(staff_tuning, "tuning-step")
        octave_text = _text(staff_tuning, "tuning-octave")
        if line <= 0 or step is None or octave_text is None:
            continue
        alter = int(float(_text(staff_tuning, "tuning-alter", "0") or "0"))
        semitone = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step]
        tunings[line] = 12 * (int(octave_text) + 1) + semitone + alter
    if not tunings:
        return None
    return [tunings[line] for line in sorted(tunings)]


def _part_metadata(root: ET.Element) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    part_list = next((node for node in root if _local(node.tag) == "part-list"), None)
    for score_part in _children(part_list, "score-part"):
        part_id = score_part.attrib.get("id", "")
        name = _text(score_part, "part-name")
        programs: list[int] = []
        for midi_instrument in _children(score_part, "midi-instrument"):
            program = _text(midi_instrument, "midi-program")
            if program:
                programs.append(int(program))
        result[part_id] = {"name": name, "programs": programs}
    return result


def _part_score(
    part: ET.Element,
    meta: dict[str, object],
    instrument: ArrangementKind,
) -> int:
    name = str(meta.get("name") or "").lower()
    programs = [int(value) for value in meta.get("programs", [])]
    tuning = _staff_tuning(part)

    if instrument == "bass":
        score = 0
        if "bass" in name:
            score += 100
        if any(33 <= program <= 40 for program in programs):
            score += 60
        if tuning and len(tuning) in {4, 5, 6} and min(tuning) < 36:
            score += 30
        return score

    if "bass" in name or any(33 <= program <= 40 for program in programs):
        return -100
    score = 0
    if any(25 <= program <= 32 for program in programs):
        score += 45
    if tuning and len(tuning) == 6:
        score += 30
    elif tuning and 5 <= len(tuning) <= 7:
        score += 10
    if "guitar" in name:
        score += 20

    if instrument == "lead":
        if "lead" in name:
            score += 100
        if "solo" in name:
            score += 80
        if "melody" in name:
            score += 35
    else:
        if "rhythm" in name or "rythm" in name:
            score += 100
        if "chord" in name:
            score += 60
        if "acoustic" in name:
            score += 25
    return score


def _select_part(
    root: ET.Element,
    explicit_index: int | None,
    instrument: ArrangementKind,
) -> tuple[int, ET.Element, dict[str, object]]:
    parts = [node for node in root if _local(node.tag) == "part"]
    metadata = _part_metadata(root)
    if not parts:
        raise ValueError("MusicXML contains no parts")
    if explicit_index is not None:
        if explicit_index < 0 or explicit_index >= len(parts):
            raise ValueError(f"MusicXML part index {explicit_index} is out of range")
        part = parts[explicit_index]
        return explicit_index, part, metadata.get(part.attrib.get("id", ""), {})

    scored: list[tuple[int, int]] = []
    for index, part in enumerate(parts):
        meta = metadata.get(part.attrib.get("id", ""), {})
        score = _part_score(part, meta, instrument)
        if score > 0:
            scored.append((score, index))
    if not scored:
        if len(parts) == 1:
            part = parts[0]
            return 0, part, metadata.get(part.attrib.get("id", ""), {})
        raise ValueError(
            f"No {instrument.capitalize()}-like MusicXML part found; pass --part-index"
        )
    best = max(score for score, _ in scored)
    winners = [index for score, index in scored if score == best]
    if len(winners) != 1:
        raise ValueError(
            f"MusicXML {instrument.capitalize()} part selection is ambiguous; pass --part-index"
        )
    index = winners[0]
    part = parts[index]
    return index, part, metadata.get(part.attrib.get("id", ""), {})


def _techniques(note: ET.Element) -> tuple[list[str], int | None, int | None]:
    techniques: list[str] = []
    for tie in _children(note, "tie"):
        tie_type = tie.attrib.get("type")
        if tie_type:
            techniques.append(f"tie_{tie_type}")
    notations = _child(note, "notations")
    technical = _child(notations, "technical")
    string_number = _text(technical, "string")
    fret_text = _text(technical, "fret")
    for name in ("hammer-on", "pull-off", "harmonic", "bend", "slide", "glissando", "trill-mark"):
        if any(_local(node.tag) == name for node in note.iter()):
            techniques.append(name.replace("-", "_"))
    if any(_local(node.tag) == "staccato" for node in note.iter()):
        techniques.append("staccato")
    return (
        sorted(set(techniques)),
        int(string_number) if string_number else None,
        int(fret_text) if fret_text else None,
    )


def _collect_part(
    part: ET.Element,
) -> tuple[
    list[_RawNote],
    list[tuple[float, float]],
    list[tuple[float, int, int]],
    list[str],
    list[int] | None,
]:
    warnings: list[str] = []
    raw_notes: list[_RawNote] = []
    tempos: list[tuple[float, float]] = []
    signatures: list[tuple[float, int, int]] = []
    tuning = _staff_tuning(part)
    string_count = len(tuning) if tuning else None
    divisions = 1
    absolute_q = 0.0

    for measure in _children(part, "measure"):
        cursor_q = absolute_q
        max_q = absolute_q
        previous_note_start = cursor_q
        attributes = _child(measure, "attributes")
        div_text = _text(attributes, "divisions")
        if div_text:
            divisions = int(div_text)
            if divisions <= 0:
                raise ValueError("MusicXML divisions must be positive")
        time_node = _child(attributes, "time")
        if time_node is not None:
            beats = _text(time_node, "beats")
            beat_type = _text(time_node, "beat-type")
            if beats and beat_type and beats.isdigit() and beat_type.isdigit():
                signatures.append((cursor_q, int(beats), int(beat_type)))
            elif beats or beat_type:
                warnings.append("Complex MusicXML time signature was not expanded")

        for element in measure:
            name = _local(element.tag)
            if name == "direction":
                sound = next(
                    (
                        node
                        for node in element.iter()
                        if _local(node.tag) == "sound" and node.attrib.get("tempo")
                    ),
                    None,
                )
                tempo: float | None = float(sound.attrib["tempo"]) if sound is not None else None
                if tempo is None:
                    per_minute = next(
                        (
                            _text(node, "per-minute")
                            for node in element.iter()
                            if _local(node.tag) == "metronome"
                        ),
                        None,
                    )
                    if per_minute:
                        tempo = float(per_minute)
                offset = _text(element, "offset")
                event_q = cursor_q + (float(offset) / divisions if offset else 0.0)
                if tempo and tempo > 0:
                    tempos.append((event_q, tempo))
            elif name == "backup":
                duration = int(_text(element, "duration", "0") or 0)
                cursor_q -= duration / divisions
            elif name == "forward":
                duration = int(_text(element, "duration", "0") or 0)
                cursor_q += duration / divisions
                max_q = max(max_q, cursor_q)
            elif name == "note":
                if _child(element, "rest") is not None:
                    duration = int(_text(element, "duration", "0") or 0)
                    if _child(element, "chord") is None:
                        cursor_q += duration / divisions
                        max_q = max(max_q, cursor_q)
                    continue
                if _child(element, "grace") is not None:
                    warnings.append("Grace notes without explicit playback duration were skipped")
                    continue
                duration_text = _text(element, "duration")
                if duration_text is None or int(duration_text) <= 0:
                    raise ValueError("MusicXML note is missing a positive duration")
                duration_q = int(duration_text) / divisions
                is_chord = _child(element, "chord") is not None
                start_q = previous_note_start if is_chord else cursor_q
                if not is_chord:
                    previous_note_start = start_q
                midi, note_name = _pitch_to_midi(element)
                techniques, xml_string, fret = _techniques(element)
                string_index: int | None = None
                if xml_string is not None:
                    if string_count is None:
                        warnings.append(
                            "Tablature string number present but staff tuning/string count is missing"
                        )
                    elif 1 <= xml_string <= string_count:
                        string_index = string_count - xml_string
                    else:
                        warnings.append(
                            f"Out-of-range MusicXML string number {xml_string} was ignored"
                        )
                raw_notes.append(
                    _RawNote(
                        start_q,
                        duration_q,
                        midi,
                        note_name,
                        string_index,
                        fret,
                        techniques,
                    )
                )
                if not is_chord:
                    cursor_q += duration_q
                    max_q = max(max_q, cursor_q)
        absolute_q = max(max_q, cursor_q)

    if any(_local(node.tag) == "repeat" for node in part.iter()):
        warnings.append(
            "MusicXML repeat structures are preserved only as written order; playback expansion is not implemented yet"
        )
    if any(
        _local(node.tag) in {"ending", "segno", "coda", "dalsegno", "dacapo"}
        for node in part.iter()
    ):
        warnings.append(
            "MusicXML navigation/repeat directives require later playback-order reconciliation"
        )
    return raw_notes, tempos, signatures, sorted(set(warnings)), tuning


def _time_at(q: float, tempos: list[tuple[float, float]]) -> float:
    events = sorted(tempos)
    current_q = 0.0
    current_bpm = 120.0
    seconds = 0.0
    for event_q, bpm in events:
        if event_q > q:
            break
        if event_q > current_q:
            seconds += (event_q - current_q) * 60.0 / current_bpm
        current_q = event_q
        current_bpm = bpm
    return seconds + (q - current_q) * 60.0 / current_bpm


def import_musicxml(
    path: Path,
    *,
    part_index: int | None = None,
    instrument: ArrangementKind = "bass",
) -> ImportedSource:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"MusicXML file not found: {path}")
    if path.suffix.lower() not in {".musicxml", ".xml", ".mxl"}:
        raise ValueError("MusicXML import supports .musicxml, .xml, and .mxl files")
    root = _load_root(path)
    if _local(root.tag) != "score-partwise":
        raise ValueError("Only score-partwise MusicXML is currently supported")

    selected_index, part, meta = _select_part(root, part_index, instrument)
    raw_notes, tempo_pairs, signature_pairs, warnings, tuning = _collect_part(part)
    if not raw_notes:
        raise ValueError("Selected MusicXML part contains no pitched notes")
    if not tempo_pairs:
        warnings.append(
            "MusicXML contains no explicit tempo; source-time conversion assumes 120 BPM until alignment"
        )
        tempo_pairs = [(0.0, 120.0)]
    elif tempo_pairs[0][0] > 0:
        warnings.append(
            "MusicXML first tempo marking occurs after song start; 120 BPM is assumed before it"
        )
        tempo_pairs.insert(0, (0.0, 120.0))

    tempo_pairs = sorted(set(tempo_pairs))
    notes = [
        SourceNoteEvent(
            start_seconds=_time_at(note.start_q, tempo_pairs),
            duration_seconds=(
                _time_at(note.start_q + note.duration_q, tempo_pairs)
                - _time_at(note.start_q, tempo_pairs)
            ),
            midi=note.midi,
            note_name=note.note_name,
            string_index=note.string_index,
            fret=note.fret,
            techniques=note.techniques,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_unverified,
            review_required=False,
        )
        for note in sorted(
            raw_notes,
            key=lambda item: (
                item.start_q,
                item.midi,
                item.string_index if item.string_index is not None else -1,
            ),
        )
    ]
    tempo_events = [
        SourceTempoEvent(
            tick=round(q * TICKS_PER_QUARTER),
            time_seconds=_time_at(q, tempo_pairs),
            bpm=bpm,
        )
        for q, bpm in tempo_pairs
    ]
    signatures = [
        SourceTimeSignatureEvent(
            tick=round(q * TICKS_PER_QUARTER),
            time_seconds=_time_at(q, tempo_pairs),
            numerator=numerator,
            denominator=denominator,
        )
        for q, numerator, denominator in sorted(set(signature_pairs))
    ]

    target_strings = 4 if instrument == "bass" else 6
    if tuning and len(tuning) != target_strings:
        warnings.append(
            f"Selected MusicXML {instrument.capitalize()} part has {len(tuning)} strings; "
            "preserved for later reconciliation"
        )

    return ImportedSource(
        provenance=SourceProvenance(
            source_type="musicxml",
            source_filename=path.name,
            source_sha256=sha256_file(path),
            importer="rocksmith-cdlc-generator/musicxml",
            importer_version=IMPORTER_VERSION,
        ),
        ticks_per_beat=TICKS_PER_QUARTER,
        tempo_events=tempo_events,
        time_signatures=signatures,
        tracks=[
            SourceTrack(
                source_track_index=selected_index,
                name=str(meta.get("name") or part.attrib.get("id") or f"Part {selected_index}"),
                instrument=instrument,
                program_numbers=[int(value) for value in meta.get("programs", [])],
                tuning_midi=tuning,
                notes=notes,
            )
        ],
        warnings=sorted(set(warnings)),
    )


def import_project_musicxml(
    project_dir: Path,
    musicxml_path: Path,
    *,
    part_index: int | None = None,
    instrument: ArrangementKind = "bass",
) -> Path:
    project_dir = project_dir.resolve()
    imported = import_musicxml(
        musicxml_path,
        part_index=part_index,
        instrument=instrument,
    )
    digest = imported.provenance.source_sha256[:12]
    stem = Path(imported.provenance.source_filename).stem.replace(" ", "-")
    suffix = f"-{instrument}" if instrument != "bass" else ""
    output = project_dir / "sources" / "imported" / f"{stem}{suffix}-{digest}.json"
    return imported.write_json(output)
