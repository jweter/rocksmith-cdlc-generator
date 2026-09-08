from __future__ import annotations

import importlib
import importlib.metadata
import hashlib
from pathlib import Path
from typing import Any, Literal

from .hashing import sha256_file
from .source_import import (
    ImportedSource,
    SourceBendPoint,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
)

_GP_QUARTER_TICKS = 960
_EOF_TRUNCATED_SUSTAIN_SECONDS = 0.001
_SUPPORTED_SUFFIXES = {".gp3", ".gp4", ".gp5"}
_BASS_PROGRAMS = set(range(32, 40))
_GUITAR_PROGRAMS = set(range(24, 32))
ArrangementKind = Literal["bass", "lead", "rhythm"]
GUITARPRO_ADAPTER_ID: Literal["pyguitarpro-adapter"] = "pyguitarpro-adapter"


class GuitarProUnavailable(RuntimeError):
    pass


class GuitarProImportError(ValueError):
    pass


def _load_guitarpro():
    try:
        return importlib.import_module("guitarpro")
    except ImportError as exc:
        raise GuitarProUnavailable(
            "Guitar Pro import requires the optional PyGuitarPro dependency. "
            "Install with `pip install -e \".[guitarpro]\"`."
        ) from exc


def guitarpro_runtime_version() -> str:
    try:
        return importlib.metadata.version("PyGuitarPro")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def guitarpro_adapter_sha256() -> str:
    """Fingerprint the complete adapter implementation for derivative evidence."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _track_program(track: Any) -> int | None:
    channel = getattr(track, "channel", None)
    program = getattr(channel, "instrument", None)
    return int(program) if program is not None else None


def _track_score(track: Any, instrument: ArrangementKind = "bass") -> int:
    name = (getattr(track, "name", "") or "").lower()
    strings = list(getattr(track, "strings", []) or [])
    program = _track_program(track)
    score = 0

    if instrument == "bass":
        if "bass" in name:
            score += 100
        if program in _BASS_PROGRAMS:
            score += 60
        if 4 <= len(strings) <= 6:
            score += 20
        if strings and min(int(getattr(s, "value", 127)) for s in strings) <= 35:
            score += 10
        return score

    if "bass" in name or program in _BASS_PROGRAMS:
        return -100
    if program in _GUITAR_PROGRAMS:
        score += 45
    if len(strings) == 6:
        score += 30
    elif 5 <= len(strings) <= 7:
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


def select_arrangement_track(
    song: Any,
    *,
    instrument: ArrangementKind,
    track_index: int | None = None,
) -> tuple[int, Any]:
    tracks = list(getattr(song, "tracks", []) or [])
    if not tracks:
        raise GuitarProImportError("Guitar Pro file contains no tracks")

    if track_index is not None:
        if track_index < 0 or track_index >= len(tracks):
            raise GuitarProImportError(f"Track index {track_index} is outside 0..{len(tracks) - 1}")
        return track_index, tracks[track_index]

    ranked = sorted(
        ((_track_score(track, instrument), index, track) for index, track in enumerate(tracks)),
        reverse=True,
        key=lambda item: item[0],
    )
    best_score = ranked[0][0]
    label = instrument.capitalize()
    if best_score <= 0:
        raise GuitarProImportError(f"No credible {label} track found; pass --track-index explicitly")
    ties = [item for item in ranked if item[0] == best_score]
    if len(ties) != 1:
        names = ", ".join(
            f"{index}:{getattr(track, 'name', '') or '<unnamed>'}" for _, index, track in ties
        )
        raise GuitarProImportError(
            f"{label} track selection is ambiguous ({names}); pass --track-index"
        )
    _, index, track = ties[0]
    return index, track


def select_bass_track(song: Any, track_index: int | None = None) -> tuple[int, Any]:
    return select_arrangement_track(song, instrument="bass", track_index=track_index)


def _normalized_tick(raw_start: Any) -> int:
    return max(0, int(raw_start or _GP_QUARTER_TICKS) - _GP_QUARTER_TICKS)


def _tempo_value(change: Any) -> float | None:
    if change is None:
        return None
    value = getattr(change, "value", change)
    try:
        bpm = float(value)
    except (TypeError, ValueError):
        return None
    return bpm if bpm > 0 else None


def _collect_tempo_points(song: Any, track: Any) -> list[tuple[int, float]]:
    points: dict[int, float] = {0: float(getattr(song, "tempo", 120) or 120)}
    for measure in getattr(track, "measures", []) or []:
        for voice in getattr(measure, "voices", []) or []:
            for beat in getattr(voice, "beats", []) or []:
                effect = getattr(beat, "effect", None)
                mix = getattr(effect, "mixTableChange", None)
                tempo = _tempo_value(getattr(mix, "tempo", None)) if mix is not None else None
                if tempo is not None:
                    points[_normalized_tick(getattr(beat, "start", 0))] = tempo
    return sorted(points.items())


def _ticks_to_seconds(tick: int, tempo_points: list[tuple[int, float]]) -> float:
    elapsed = 0.0
    current_tick = 0
    current_bpm = tempo_points[0][1]
    for change_tick, bpm in tempo_points[1:]:
        if change_tick >= tick:
            break
        elapsed += (change_tick - current_tick) / _GP_QUARTER_TICKS * (60.0 / current_bpm)
        current_tick = change_tick
        current_bpm = bpm
    elapsed += (tick - current_tick) / _GP_QUARTER_TICKS * (60.0 / current_bpm)
    return elapsed


def _string_map(track: Any) -> tuple[list[int], dict[int, int], dict[int, int]]:
    strings = list(getattr(track, "strings", []) or [])
    if not strings:
        raise GuitarProImportError("Selected Guitar Pro track has no string tuning")
    rows = [(int(getattr(s, "number")), int(getattr(s, "value"))) for s in strings]
    rows.sort(key=lambda item: item[0], reverse=True)
    tuning = [open_midi for _, open_midi in rows]
    neutral_index = {number: index for index, (number, _) in enumerate(rows)}
    open_pitch = {number: midi for number, midi in rows}
    return tuning, neutral_index, open_pitch


SLIDE_KIND_LABELS = {
    "intoFromAbove": "into_from_above",
    "intoFromBelow": "into_from_below",
    "shiftSlideTo": "shift",
    "legatoSlideTo": "legato",
    "outDownwards": "out_downwards",
    "outUpwards": "out_upwards",
}


def _slide_kinds(note: Any) -> list[str]:
    effect = getattr(note, "effect", None)
    slides = list(getattr(effect, "slides", None) or []) if effect is not None else []
    kinds = []
    for slide in slides:
        name = str(getattr(slide, "name", ""))
        label = SLIDE_KIND_LABELS.get(name)
        if label is not None and label not in kinds:
            kinds.append(label)
    return kinds


_PITCHED_SLIDE_KINDS = frozenset({"shift", "legato"})


def _resolve_slide_target_frets(notes: list[SourceNoteEvent]) -> list[SourceNoteEvent]:
    by_string: dict[int, list[int]] = {}
    for index, note in enumerate(notes):
        if note.string_index is not None:
            by_string.setdefault(note.string_index, []).append(index)

    resolved = list(notes)
    for indices in by_string.values():
        for position, note_index in enumerate(indices):
            note = notes[note_index]
            slide_kinds = set(note.slide_kinds)
            if not (slide_kinds & _PITCHED_SLIDE_KINDS):
                continue
            for next_index in indices[position + 1 :]:
                next_note = notes[next_index]
                if next_note.start_seconds <= note.start_seconds:
                    continue
                if next_note.fret is None:
                    break
                updates: dict[str, Any] = {"slide_target_fret": next_note.fret}
                if "legato" in slide_kinds:
                    updates["link_next"] = True
                resolved[note_index] = note.model_copy(update=updates)
                break
    return resolved


def _resolve_hammer_pulloff_direction(notes: list[SourceNoteEvent]) -> list[SourceNoteEvent]:
    by_string: dict[int, list[int]] = {}
    for index, note in enumerate(notes):
        if note.string_index is not None:
            by_string.setdefault(note.string_index, []).append(index)

    resolved = list(notes)
    for indices in by_string.values():
        for position, note_index in enumerate(indices):
            note = notes[note_index]
            if "hammer_on_pull_off" not in note.techniques or position == 0:
                continue
            previous_note = notes[indices[position - 1]]
            if (
                previous_note.fret is None
                or note.fret is None
                or note.fret == previous_note.fret
            ):
                continue
            direction = "hammer_on" if note.fret > previous_note.fret else "pull_off"
            techniques = [
                direction if technique == "hammer_on_pull_off" else technique
                for technique in note.techniques
            ]
            resolved[note_index] = note.model_copy(update={"techniques": techniques})
    return resolved


def _bend_points(note: Any) -> list[SourceBendPoint]:
    effect = getattr(note, "effect", None)
    bend = getattr(effect, "bend", None) if effect is not None else None
    points = list(getattr(bend, "points", None) or []) if bend is not None else []
    if not points:
        return []
    max_position = float(getattr(type(bend), "maxPosition", 12) or 12)
    return [
        SourceBendPoint(
            position=max(0.0, min(1.0, float(getattr(point, "position", 0)) / max_position)),
            semitones=float(getattr(point, "value", 0)),
            vibrato=bool(getattr(point, "vibrato", False)),
        )
        for point in points
    ]


def _techniques(note: Any) -> list[str]:
    effect = getattr(note, "effect", None)
    if effect is None:
        return []
    flags = {
        "hammer": "hammer_on_pull_off",
        "palmMute": "palm_mute",
        "staccato": "staccato",
        "letRing": "let_ring",
        "vibrato": "vibrato",
        "ghostNote": "ghost_note",
        "accentuatedNote": "accent",
        "heavyAccentuatedNote": "heavy_accent",
    }
    result = [label for attr, label in flags.items() if bool(getattr(effect, attr, False))]
    if getattr(effect, "bend", None) is not None:
        result.append("bend")
    harmonic = getattr(effect, "harmonic", None)
    if harmonic is not None:
        if int(getattr(harmonic, "type", 1) or 1) == 1:
            result.append("harmonic")
        else:
            result.append("harmonic_pinch")
    if getattr(effect, "grace", None) is not None:
        result.append("grace")
    if getattr(effect, "trill", None) is not None:
        result.append("trill")
    if getattr(effect, "tremoloPicking", None) is not None:
        result.append("tremolo_picking")
    if getattr(effect, "slides", None):
        result.append("slide")
    note_type = str(getattr(getattr(note, "type", None), "name", "")).lower()
    if "tie" in note_type:
        result.append("tie")
    return sorted(set(result))


def _eof_default_sustain_seconds(
    source_note: Any,
    *,
    beat_note_count: int,
    duration_ticks: int,
    natural_sustain_seconds: float,
) -> float:
    """Apply EOF's default GP short-note sustain preference at import time.

    Audited from raynebc/editor-on-fire src/gp_import.c eof_load_gp at
    c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100. EOF defaults to truncating
    eligible short single notes while leaving short chords untruncated.
    """
    if beat_note_count != 1:
        return natural_sustain_seconds
    effect = getattr(source_note, "effect", None)
    techniques = set(_techniques(source_note))
    is_dead = str(getattr(getattr(source_note, "type", None), "name", "")).lower() == "dead"
    muted = is_dead or bool(getattr(effect, "palmMute", False))
    short_or_staccato = duration_ticks < _GP_QUARTER_TICKS or bool(getattr(effect, "staccato", False))
    tremolo = getattr(effect, "tremoloPicking", None) is not None
    technique_exempt = (
        "bend" in techniques
        or "vibrato" in techniques
        or "slide" in techniques
    )
    truncate = (muted or (short_or_staccato and not tremolo)) and not technique_exempt
    return min(natural_sustain_seconds, _EOF_TRUNCATED_SUSTAIN_SECONDS) if truncate else natural_sustain_seconds


def _time_signatures(track: Any, tempo_points: list[tuple[int, float]]) -> list[SourceTimeSignatureEvent]:
    events: list[SourceTimeSignatureEvent] = []
    seen: set[tuple[int, int, int]] = set()
    for measure in getattr(track, "measures", []) or []:
        header = getattr(measure, "header", None)
        signature = getattr(header, "timeSignature", None)
        if signature is None:
            continue
        numerator = int(getattr(signature, "numerator", 4))
        denominator_obj = getattr(signature, "denominator", 4)
        denominator = int(getattr(denominator_obj, "value", denominator_obj))
        tick = _normalized_tick(getattr(header, "start", _GP_QUARTER_TICKS))
        key = (tick, numerator, denominator)
        if key in seen:
            continue
        seen.add(key)
        events.append(
            SourceTimeSignatureEvent(
                tick=tick,
                time_seconds=_ticks_to_seconds(tick, tempo_points),
                numerator=numerator,
                denominator=denominator,
            )
        )
    return sorted(events, key=lambda event: event.tick)


def convert_guitarpro_song(
    song: Any,
    *,
    source_path: Path,
    source_sha256: str,
    track_index: int | None = None,
    instrument: ArrangementKind = "bass",
    importer_version: str = "unknown",
) -> ImportedSource:
    selected_index, track = select_arrangement_track(
        song,
        instrument=instrument,
        track_index=track_index,
    )
    tuning, string_index_by_number, open_pitch_by_number = _string_map(track)
    tempo_points = _collect_tempo_points(song, track)
    warnings: list[str] = []

    target_strings = 4 if instrument == "bass" else 6
    if len(tuning) != target_strings:
        warnings.append(
            f"Selected {instrument.capitalize()} track has {len(tuning)} strings; "
            f"Rocksmith {instrument.capitalize()} export currently targets {target_strings} strings."
        )
    headers = list(getattr(song, "measureHeaders", []) or [])
    if any(
        bool(getattr(header, "isRepeatOpen", False))
        or int(getattr(header, "repeatClose", 0) or 0) > 0
        for header in headers
    ):
        warnings.append("Guitar Pro repeat structure is not unfolded yet; imported events use written score order.")

    notes: list[SourceNoteEvent] = []
    active_voice_count = 0
    for measure in getattr(track, "measures", []) or []:
        for voice in getattr(measure, "voices", []) or []:
            beats = [beat for beat in (getattr(voice, "beats", []) or []) if getattr(beat, "notes", None)]
            if beats:
                active_voice_count += 1
            for beat in beats:
                start_tick = _normalized_tick(getattr(beat, "start", 0))
                duration_obj = getattr(beat, "duration", None)
                duration_ticks = int(getattr(duration_obj, "time", 0) or 0)
                if duration_ticks <= 0:
                    raise GuitarProImportError("Encountered Guitar Pro beat with non-positive duration")
                start_seconds = _ticks_to_seconds(start_tick, tempo_points)
                end_seconds = _ticks_to_seconds(start_tick + duration_ticks, tempo_points)
                beat_notes = list(getattr(beat, "notes", []) or [])
                natural_sustain_seconds = end_seconds - start_seconds
                for source_note in beat_notes:
                    string_number = int(getattr(source_note, "string"))
                    if string_number not in open_pitch_by_number:
                        raise GuitarProImportError(
                            f"Note references unknown Guitar Pro string {string_number}"
                        )
                    fret = int(getattr(source_note, "value"))
                    midi = open_pitch_by_number[string_number] + fret
                    techniques = _techniques(source_note)
                    notes.append(
                        SourceNoteEvent(
                            start_seconds=start_seconds,
                            duration_seconds=_eof_default_sustain_seconds(
                                source_note,
                                beat_note_count=len(beat_notes),
                                duration_ticks=duration_ticks,
                                natural_sustain_seconds=natural_sustain_seconds,
                            ),
                            midi=midi,
                            note_name=None,
                            string_index=string_index_by_number[string_number],
                            fret=fret,
                            techniques=techniques,
                            import_confidence=1.0,
                            review_required="tie" in techniques,
                            slide_kinds=_slide_kinds(source_note),
                            bend_points=_bend_points(source_note),
                        )
                    )

    if active_voice_count > len(getattr(track, "measures", []) or []):
        warnings.append("Multiple active Guitar Pro voices were preserved; polyphonic/voice conflicts require reconciliation.")
    notes.sort(
        key=lambda item: (
            item.start_seconds,
            item.string_index if item.string_index is not None else 99,
            item.midi,
        )
    )
    if not notes:
        raise GuitarProImportError(
            f"Selected Guitar Pro {instrument.capitalize()} track contains no notes"
        )
    notes = _resolve_slide_target_frets(notes)
    notes = _resolve_hammer_pulloff_direction(notes)

    tempo_events = [
        SourceTempoEvent(
            tick=tick,
            time_seconds=_ticks_to_seconds(tick, tempo_points),
            bpm=bpm,
        )
        for tick, bpm in tempo_points
    ]
    track_model = SourceTrack(
        source_track_index=selected_index,
        name=getattr(track, "name", None),
        instrument=instrument,
        channel_numbers=[int(getattr(getattr(track, "channel", None), "channel", 0))],
        program_numbers=[_track_program(track)] if _track_program(track) is not None else [],
        tuning_midi=tuning,
        capo=int(getattr(track, "offset", 0) or 0),
        notes=notes,
    )
    return ImportedSource(
        provenance=SourceProvenance(
            source_type=source_path.suffix.lower().lstrip("."),
            source_filename=source_path.name,
            source_sha256=source_sha256,
            importer=GUITARPRO_ADAPTER_ID,
            importer_version=importer_version,
        ),
        ticks_per_beat=_GP_QUARTER_TICKS,
        tempo_events=tempo_events,
        time_signature_events=_time_signatures(track, tempo_points),
        tracks=[track_model],
        warnings=warnings,
    )


def import_guitarpro(
    path: Path,
    *,
    track_index: int | None = None,
    instrument: ArrangementKind = "bass",
) -> ImportedSource:
    stored = Path(path)
    if not stored.exists() or not stored.is_file():
        raise GuitarProImportError(f"Guitar Pro file does not exist: {stored}")
    if stored.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise GuitarProImportError("Guitar Pro import supports .gp3, .gp4, and .gp5")
    guitarpro = _load_guitarpro()
    try:
        song = guitarpro.parse(str(stored))
    except Exception as exc:  # noqa: BLE001
        raise GuitarProImportError(f"Failed to parse Guitar Pro file: {stored.name}") from exc
    return convert_guitarpro_song(
        song,
        source_path=stored,
        source_sha256=sha256_file(stored),
        track_index=track_index,
        instrument=instrument,
        importer_version=guitarpro_runtime_version(),
    )
