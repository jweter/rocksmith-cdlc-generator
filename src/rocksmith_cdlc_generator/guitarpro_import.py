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

    # Reject obvious Bass tracks from guitar auto-selection even if they happen to
    # use six strings. Explicit --track-index remains available for unusual scores.
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
    # Guitar Pro string 1 is the highest physical string. The canonical model and
    # Rocksmith use low-string-first indices, so physical identity is obtained by
    # reversing GP string numbers. Never sort by pitch: re-entrant/crossed tunings
    # are allowed to be non-monotonic.
    rows.sort(key=lambda item: item[0], reverse=True)
    tuning = [open_midi for _, open_midi in rows]
    neutral_index = {number: index for index, (number, _) in enumerate(rows)}
    open_pitch = {number: midi for number, midi in rows}
    return tuning, neutral_index, open_pitch


# PyGuitarPro's guitarpro.models.SlideType enumerates six distinct slide subtypes (audited
# directly from PyGuitarPro's own source, not GP's raw file format): two "into" slides that
# approach the note from a semitone above/below without a defined start pitch, two "out" slides
# that leave the note without a defined end pitch, and two "to a specific target" slides (shift
# vs. legato, i.e. picked vs. hammered-into the destination note). Previously this project's
# _techniques() collapsed all six into one generic "slide" flag; that flag is left unchanged
# here (existing validation in eof_rocksmith_validation.py and reviewed_techniques.py already
# depends on that exact string) and the specific subtype(s), if any, are captured separately.
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


def _bend_points(note: Any) -> list[SourceBendPoint]:
    """Extract a note's bend curve, already normalized by PyGuitarPro to real-world units.

    PyGuitarPro's own GP file decoding (``guitarpro/gp3.py:readBend``) converts each raw point's
    position from GP's 0..60 tick scale to ``BendEffect.maxPosition`` (12) and its value from
    GP's 25-raw-units-per-semitone scale to whole semitones (``round(rawValue / 25)``) before it
    ever reaches this project's importer -- there is no separate quarter-step/half-step byte
    encoding to decode here (that is EOF's own internal bend-note storage format, specific to its
    C data model, not something PyGuitarPro's already-normalized BendPoint exposes). This
    function only re-scales PyGuitarPro's 0..12 position axis to this project's 0.0..1.0
    fraction-of-note-duration convention.
    """

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
        # raynebc/editor-on-fire src/gp_import.c (audited at c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100)
        # reads GP's raw harmonic-type byte (1=natural, 2=artificial, 3=tapped, 4=pinch,
        # 5=semi -- confirmed to match PyGuitarPro's HarmonicEffect.type 1:1 by reading
        # PyGuitarPro's own model source) and sets EOF_PRO_GUITAR_NOTE_FLAG_HARMONIC only for
        # type 1; every other type sets EOF_PRO_GUITAR_NOTE_FLAG_P_HARMONIC instead, under the
        # default (0) value of the eof_gp_import_nat_harmonics_only preference in src/main.c.
        # This project previously tagged every harmonic type as the same generic "harmonic"
        # label, which rocksmith_xml.py exports as the RS XML `harmonic` attribute even for a
        # pinch harmonic -- rs.c's own export instead sets a separate `harmonicPinch` attribute
        # for exactly this non-natural set. "harmonic" is kept for natural harmonics (existing
        # XML export path unchanged); "harmonic_pinch" is new and additive.
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
                for source_note in getattr(beat, "notes", []) or []:
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
                            duration_seconds=end_seconds - start_seconds,
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
        time_signatures=_time_signatures(track, tempo_points),
        tracks=[track_model],
        warnings=warnings,
    )


def import_guitarpro(
    path: Path,
    *,
    track_index: int | None = None,
    instrument: ArrangementKind = "bass",
) -> ImportedSource:
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
        instrument=instrument,
        importer_version=guitarpro_runtime_version(),
    )


def import_project_guitarpro(
    project_dir: Path,
    gp_path: Path,
    *,
    track_index: int | None = None,
    instrument: ArrangementKind = "bass",
) -> Path:
    project_dir = project_dir.resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"Project manifest not found: {project_dir / 'project.json'}")
    imported = import_guitarpro(
        gp_path,
        track_index=track_index,
        instrument=instrument,
    )
    stem = Path(imported.provenance.source_filename).stem
    destination = (
        project_dir
        / "sources"
        / "imported"
        / f"{stem}-{instrument}-{imported.provenance.source_sha256[:12]}.json"
    )
    return imported.write_json(destination)
