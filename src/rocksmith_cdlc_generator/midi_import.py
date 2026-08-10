from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from statistics import median
from typing import Literal

from mido import MidiFile

from .hashing import sha256_file
from .source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
)


class MidiImportError(ValueError):
    pass


ArrangementKind = Literal["bass", "lead", "rhythm"]
_PITCH_CLASSES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_GM_BASS_PROGRAMS = set(range(32, 40))
_GM_GUITAR_PROGRAMS = set(range(24, 32))


def _note_name(midi_note: int) -> str:
    return f"{_PITCH_CLASSES[midi_note % 12]}{midi_note // 12 - 1}"


def _absolute_messages(track):
    tick = 0
    for message in track:
        tick += message.time
        yield tick, message


def _normalized_tempo_events(midi: MidiFile) -> list[tuple[int, int]]:
    events: list[tuple[int, int, int]] = []
    order = 0
    for track in midi.tracks:
        for tick, message in _absolute_messages(track):
            if message.type == "set_tempo":
                events.append((tick, order, int(message.tempo)))
                order += 1

    events.sort(key=lambda item: (item[0], item[1]))
    by_tick: dict[int, int] = {0: 500_000}
    for tick, _, tempo in events:
        by_tick[tick] = tempo
    return sorted(by_tick.items())


def _tick_to_seconds(tick: int, tempo_events: list[tuple[int, int]], ticks_per_beat: int) -> float:
    seconds = 0.0
    previous_tick = 0
    current_tempo = 500_000
    for event_tick, event_tempo in tempo_events:
        if event_tick > tick:
            break
        if event_tick > previous_tick:
            seconds += (event_tick - previous_tick) * current_tempo / 1_000_000 / ticks_per_beat
        previous_tick = event_tick
        current_tempo = event_tempo
    if tick > previous_tick:
        seconds += (tick - previous_tick) * current_tempo / 1_000_000 / ticks_per_beat
    return seconds


def _track_features(track) -> dict[str, object]:
    names: list[str] = []
    programs: set[int] = set()
    channels: set[int] = set()
    pitches: list[int] = []

    for _, message in _absolute_messages(track):
        if message.type == "track_name" and message.name.strip():
            names.append(message.name.strip())
        elif message.type == "instrument_name" and message.name.strip():
            names.append(message.name.strip())
        elif message.type == "program_change":
            programs.add(int(message.program))
            channels.add(int(message.channel))
        elif message.type == "note_on" and message.velocity > 0:
            pitches.append(int(message.note))
            channels.add(int(message.channel))

    name = " / ".join(dict.fromkeys(names)) or None
    return {
        "name": name,
        "programs": sorted(programs),
        "channels": sorted(channels),
        "pitches": pitches,
    }


def _arrangement_score(features: dict[str, object], instrument: ArrangementKind) -> tuple[int, int, int, int]:
    name = str(features["name"] or "").lower()
    programs = set(features["programs"])
    pitches = list(features["pitches"])

    if instrument == "bass":
        return (
            1 if "bass" in name else 0,
            1 if programs & _GM_BASS_PROGRAMS else 0,
            1 if pitches and median(pitches) <= 55 else 0,
            0,
        )

    if "bass" in name or programs & _GM_BASS_PROGRAMS:
        return (-1, -1, -1, -1)

    role_name = 0
    if instrument == "lead":
        if "lead" in name:
            role_name = 3
        elif "solo" in name:
            role_name = 2
        elif "melody" in name:
            role_name = 1
    else:
        if "rhythm" in name or "rythm" in name:
            role_name = 3
        elif "chord" in name:
            role_name = 2
        elif "acoustic" in name:
            role_name = 1

    return (
        role_name,
        1 if "guitar" in name else 0,
        1 if programs & _GM_GUITAR_PROGRAMS else 0,
        1 if pitches and median(pitches) >= 48 else 0,
    )


def _select_track(
    midi: MidiFile,
    explicit_index: int | None,
    instrument: ArrangementKind,
) -> tuple[int, dict[str, object]]:
    candidates: list[tuple[int, dict[str, object]]] = []
    for index, track in enumerate(midi.tracks):
        features = _track_features(track)
        if features["pitches"]:
            candidates.append((index, features))

    if not candidates:
        raise MidiImportError("MIDI contains no note events")

    if explicit_index is not None:
        if explicit_index < 0 or explicit_index >= len(midi.tracks):
            raise MidiImportError(f"MIDI track index {explicit_index} is out of range")
        features = _track_features(midi.tracks[explicit_index])
        if not features["pitches"]:
            raise MidiImportError(f"MIDI track {explicit_index} contains no note events")
        return explicit_index, features

    if len(candidates) == 1:
        return candidates[0]

    scored = sorted(
        ((_arrangement_score(features, instrument), index, features) for index, features in candidates),
        key=lambda item: (item[0], -item[1]),
        reverse=True,
    )
    best_score = scored[0][0]
    best = [item for item in scored if item[0] == best_score]
    empty_score = (0, 0, 0, 0)
    if best_score <= empty_score or len(best) != 1:
        descriptions = ", ".join(
            f"{index}:{features['name'] or '<unnamed>'}" for _, index, features in scored
        )
        raise MidiImportError(
            f"{instrument.capitalize()} track selection is ambiguous. Pass --track-index explicitly. "
            f"Candidate tracks: {descriptions}"
        )
    _, index, features = best[0]
    return index, features


def _select_bass_track(midi: MidiFile, explicit_index: int | None) -> tuple[int, dict[str, object]]:
    return _select_track(midi, explicit_index, "bass")


def import_midi(
    path: Path,
    *,
    track_index: int | None = None,
    instrument: ArrangementKind = "bass",
) -> ImportedSource:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"MIDI file not found: {path}")

    try:
        midi = MidiFile(path)
    except Exception as exc:  # Mido raises several parser-specific exception types.
        raise MidiImportError(f"Could not parse MIDI file {path.name}: {exc}") from exc

    if midi.ticks_per_beat <= 0:
        raise MidiImportError("SMPTE-timed MIDI files are not supported in the first importer")

    tempo_pairs = _normalized_tempo_events(midi)
    selected_index, features = _select_track(midi, track_index, instrument)
    selected_track = midi.tracks[selected_index]

    active: dict[tuple[int, int], deque[int]] = defaultdict(deque)
    notes: list[SourceNoteEvent] = []
    for tick, message in _absolute_messages(selected_track):
        if message.type == "note_on" and message.velocity > 0:
            active[(int(message.channel), int(message.note))].append(tick)
            continue
        if message.type not in {"note_off", "note_on"}:
            continue
        if message.type == "note_on" and message.velocity > 0:
            continue

        key = (int(message.channel), int(message.note))
        starts = active.get(key)
        if not starts:
            raise MidiImportError(
                f"Malformed MIDI track {selected_index}: note-off without matching note-on "
                f"for channel {key[0]} pitch {key[1]} at tick {tick}"
            )
        start_tick = starts.popleft()
        start_seconds = _tick_to_seconds(start_tick, tempo_pairs, midi.ticks_per_beat)
        end_seconds = _tick_to_seconds(tick, tempo_pairs, midi.ticks_per_beat)
        duration = end_seconds - start_seconds
        if duration <= 0:
            raise MidiImportError(
                f"Malformed MIDI track {selected_index}: non-positive duration for pitch {key[1]}"
            )
        notes.append(
            SourceNoteEvent(
                start_seconds=start_seconds,
                duration_seconds=duration,
                midi=key[1],
                note_name=_note_name(key[1]),
                import_confidence=1.0,
            )
        )

    unclosed = [(channel, pitch, len(starts)) for (channel, pitch), starts in active.items() if starts]
    if unclosed:
        raise MidiImportError(f"Malformed MIDI track {selected_index}: unclosed note events {unclosed}")

    notes.sort(key=lambda note: (note.start_seconds, note.midi, note.duration_seconds))
    tempo_events = [
        SourceTempoEvent(
            tick=tick,
            time_seconds=_tick_to_seconds(tick, tempo_pairs, midi.ticks_per_beat),
            bpm=60_000_000 / tempo,
        )
        for tick, tempo in tempo_pairs
    ]

    time_signatures: list[SourceTimeSignatureEvent] = []
    seen_signatures: set[tuple[int, int, int]] = set()
    for track in midi.tracks:
        for tick, message in _absolute_messages(track):
            if message.type != "time_signature":
                continue
            key = (tick, int(message.numerator), int(message.denominator))
            if key in seen_signatures:
                continue
            seen_signatures.add(key)
            time_signatures.append(
                SourceTimeSignatureEvent(
                    tick=tick,
                    time_seconds=_tick_to_seconds(tick, tempo_pairs, midi.ticks_per_beat),
                    numerator=int(message.numerator),
                    denominator=int(message.denominator),
                )
            )
    time_signatures.sort(key=lambda event: (event.tick, event.numerator, event.denominator))

    return ImportedSource(
        provenance=SourceProvenance(
            source_type="midi",
            source_filename=path.name,
            source_sha256=sha256_file(path),
            importer="mido-midi",
            importer_version="2",
        ),
        ticks_per_beat=midi.ticks_per_beat,
        tempo_events=tempo_events,
        time_signatures=time_signatures,
        tracks=[
            SourceTrack(
                source_track_index=selected_index,
                name=features["name"],
                instrument=instrument,
                channel_numbers=features["channels"],
                program_numbers=features["programs"],
                notes=notes,
            )
        ],
    )


def import_project_midi(
    project_dir: Path,
    midi_path: Path,
    *,
    track_index: int | None = None,
    instrument: ArrangementKind = "bass",
) -> Path:
    project_dir = project_dir.resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project_dir}")

    imported = import_midi(
        midi_path,
        track_index=track_index,
        instrument=instrument,
    )
    stem = Path(imported.provenance.source_filename).stem
    suffix = f"-{instrument}" if instrument != "bass" else ""
    output = (
        project_dir
        / "sources"
        / "imported"
        / f"{stem}{suffix}-{imported.provenance.source_sha256[:12]}.json"
    )
    return imported.write_json(output)
