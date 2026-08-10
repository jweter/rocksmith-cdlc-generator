from __future__ import annotations

import importlib
import importlib.metadata
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
)

_GP_QUARTER_TICKS = 960
_SUPPORTED_SUFFIXES = {".gp3", ".gp4", ".gp5"}
_BASS_PROGRAMS = set(range(32, 40))


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


def _importer_version() -> str:
    try:
        return importlib.metadata.version("PyGuitarPro")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _track_program(track: Any) -> int | None:
    channel = getattr(track, "channel", None)
    program = getattr(channel, "instrument", None)
    return int(program) if program is not None else None


def _track_score(track: Any) -> int:
    name = (getattr(track, "name", "") or "").lower()
    strings = list(getattr(track, "strings", []) or [])
    program = _track_program(track)
    score = 0
    if "bass" in name:
        score += 100
    if program in _BASS_PROGRAMS:
        score += 60
    if 4 <= len(strings) <= 6:
        score += 20
    if strings and min(int(getattr(s, "value", 127)) for s in strings) <= 35:
        score += 10
    return score


def select_bass_track(song: Any, track_index: int | None = None) -> tuple[int, Any]:
    tracks = list(getattr(song, "tracks", []) or [])
    if not tracks:
        raise GuitarProImportError("Guitar Pro file contains no tracks")

    if track_index is not None:
        if track_index < 0 or track_index >= len(tracks):
            raise GuitarProImportError(f"Track index {track_index} is outside 0..{len(tracks) - 1}")
        return track_index, tracks[track_index]

    ranked = sorted(((_track_score(track), index, track) for index, track in enumerate(tracks)), reverse=True, key=lambda x: x[0])
    best_score = ranked[0][0]
    if best_score <= 0:
        raise GuitarProImportError("No credible Bass track found; pass --track-index explicitly")
    ties = [item for item in ranked if item[0] == best_score]
    if len(ties) != 1:
        names = ", ".join(f"{index}:{getattr(track, 'name', '') or '<unnamed>'}" for _, index, track in ties)
        raise GuitarProImportError(f"Bass track selection is ambiguous ({names}); pass --track-index")
    _, index, track = ties[0]
    return index, track


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
    rows.sort(key=lambda item: (item[1], item[0]))
    tuning = [open_midi for _, open_midi in rows]
    neutral_index = {number: index for index, (number, _) in enumerate(rows)}
    open_pitch = {number: midi for number, midi in rows}
    return tuning, neutral_index, open_pitch


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
    if getattr(effect, "harmonic", None) is not None:
        result.append("harmonic")
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
        events.append(SourceTimeSignatureEvent(
            tick=tick,
            time_seconds=_ticks_to_seconds(tick, tempo_points),
            numerator=numerator,
            denominator=denominator,
        ))
    return sorted(events, key=lambda e: e.tick)


def convert_guitarpro_song(song: Any, *, source_path: Path, source_sha256: str, track_index: int | None = None, importer_version: str = "unknown") -> ImportedSource:
    selected_index, track = select_bass_track(song, track_index)
    tuning, string_index_by_number, open_pitch_by_number = _string_map(track)
    tempo_points = _collect_tempo_points(song, track)
    warnings: list[str] = []

    if len(tuning) != 4:
        warnings.append(f"Selected Bass track has {len(tuning)} strings; Rocksmith Bass export currently targets four strings.")
    headers = list(getattr(song, "measureHeaders", []) or [])
    if any(bool(getattr(header, "isRepeatOpen", False)) or int(getattr(header, "repeatClose", 0) or 0) > 0 for header in headers):
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
                for note in getattr(beat, "notes", []) or []:
                    string_number = int(getattr(note, "string"))
                    if string_number not in open_pitch_by_number:
                        raise GuitarProImportError(f"Note references unknown Guitar Pro string {string_number}")
                    fret = int(getattr(note, "value"))
                    midi = open_pitch_by_number[string_number] + fret
                    techniques = _techniques(note)
                    review = "tie" in techniques
                    notes.append(SourceNoteEvent(
                        start_seconds=start_seconds,
                        duration_seconds=end_seconds - start_seconds,
                        midi=midi,
                        note_name=None,
                        string_index=string_index_by_number[string_number],
                        fret=fret,
                        techniques=techniques,
                        import_confidence=1.0,
                        review_required=review,
                    ))

    if active_voice_count > len(getattr(track, "measures", []) or []):
        warnings.append("Multiple active Guitar Pro voices were preserved; polyphonic/voice conflicts require reconciliation.")
    notes.sort(key=lambda note: (note.start_seconds, note.string_index if note.string_index is not None else 99, note.midi))
    if not notes:
        raise GuitarProImportError("Selected Guitar Pro Bass track contains no notes")

    tempo_events = [
        SourceTempoEvent(tick=tick, time_seconds=_ticks_to_seconds(tick, tempo_points), bpm=bpm)
        for tick, bpm in tempo_points
    ]
    track_model = SourceTrack(
        source_track_index=selected_index,
        name=getattr(track, "name", None),
        instrument="bass",
        channel_numbers=[int(getattr(getattr(track, "channel", None), "channel", 0))],
        program_numbers=[_track_program(track)] if _track_program(track) is not None else [],
        tuning_midi=tuning,
        notes=notes,
    )
    return ImportedSource(
        provenance=SourceProvenance(
            source_type=source_path.suffix.lower().lstrip("."),
            source_filename=source_path.name,
            source_sha256=source_sha256,
            importer="pyguitarpro-adapter",
            importer_version=importer_version,
        ),
        ticks_per_beat=_GP_QUARTER_TICKS,
        tempo_events=tempo_events,
        time_signatures=_time_signatures(track, tempo_points),
        tracks=[track_model],
        warnings=warnings,
    )


def import_guitarpro(path: Path, *, track_index: int | None = None) -> ImportedSource:
    path = path.resolve()
    if path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise GuitarProImportError("Guitar Pro importer supports .gp3, .gp4, and .gp5")
    if not path.is_file():
        raise FileNotFoundError(path)
    guitarpro = _load_guitarpro()
    try:
        song = guitarpro.parse(str(path))
    except Exception as exc:
        raise GuitarProImportError(f"Failed to parse Guitar Pro file: {path.name}") from exc
    return convert_guitarpro_song(
        song,
        source_path=path,
        source_sha256=sha256_file(path),
        track_index=track_index,
        importer_version=_importer_version(),
    )


def import_project_guitarpro(project_dir: Path, gp_path: Path, *, track_index: int | None = None) -> Path:
    project_dir = project_dir.resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"Project manifest not found: {project_dir / 'project.json'}")
    imported = import_guitarpro(gp_path, track_index=track_index)
    stem = Path(imported.provenance.source_filename).stem
    destination = project_dir / "sources" / "imported" / f"{stem}-{imported.provenance.source_sha256[:12]}.json"
    return imported.write_json(destination)
