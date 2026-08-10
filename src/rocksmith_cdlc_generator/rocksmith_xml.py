from __future__ import annotations

from pathlib import Path
from statistics import mean
from xml.etree import ElementTree as ET

from .beats import TempoMap
from .fret_mapping import BassMapping, MappedNote
from .guitar_authoring import GuitarAuthoringChart, GuitarAuthoringNote
from .models import ProjectManifest

_STANDARD_BASS_OPEN_MIDI = (28, 33, 38, 43)
_STANDARD_GUITAR_OPEN_MIDI = (40, 45, 50, 55, 59, 64)

_ARRANGEMENT_PROPERTY_NAMES = (
    "represent",
    "bonusArr",
    "standardTuning",
    "nonStandardChords",
    "barreChords",
    "powerChords",
    "dropDPower",
    "openChords",
    "fingerPicking",
    "pickDirection",
    "doubleStops",
    "palmMutes",
    "harmonics",
    "pinchHarmonics",
    "hopo",
    "tremolo",
    "slides",
    "unpitchedSlides",
    "bends",
    "tapping",
    "vibrato",
    "fretHandMutes",
    "slapPop",
    "twoFingerPicking",
    "fifthsAndOctaves",
    "syncopation",
    "bassPick",
    "sustain",
    "pathLead",
    "pathRhythm",
    "pathBass",
)

# These imported technique labels can be represented without inventing
# direction, target fret, bend curves, or other missing performance data.
DIRECT_NOTE_TECHNIQUES = frozenset(
    {"accent", "heavy_accent", "harmonic", "palm_mute", "tremolo_picking", "vibrato"}
)


def rocksmith_tuning_offsets(mapping: BassMapping) -> tuple[int, int, int, int, int, int]:
    """Convert absolute Bass open-string MIDI pitches to Rocksmith semitone offsets."""
    bass_offsets = tuple(
        actual - standard
        for actual, standard in zip(mapping.tuning.open_midi, _STANDARD_BASS_OPEN_MIDI)
    )
    return (*bass_offsets, 0, 0)


def rocksmith_guitar_tuning_offsets(
    chart: GuitarAuthoringChart,
) -> tuple[int, int, int, int, int, int]:
    """Convert explicit six-string guitar tuning into Rocksmith semitone offsets."""
    return tuple(
        actual - standard
        for actual, standard in zip(chart.tuning_midi, _STANDARD_GUITAR_OPEN_MIDI)
    )


def unsupported_note_techniques(note: MappedNote | GuitarAuthoringNote) -> list[str]:
    """Return imported techniques this exporter cannot encode losslessly yet."""
    return sorted(set(note.techniques) - DIRECT_NOTE_TECHNIQUES)


def _technique_attributes(note: MappedNote | GuitarAuthoringNote) -> dict[str, str]:
    techniques = set(note.techniques)
    attributes: dict[str, str] = {}
    if "palm_mute" in techniques:
        attributes["palmMute"] = "1"
    if "harmonic" in techniques:
        attributes["harmonic"] = "1"
    if "tremolo_picking" in techniques:
        attributes["tremolo"] = "1"
    if "accent" in techniques or "heavy_accent" in techniques:
        attributes["accent"] = "1"
    if "vibrato" in techniques:
        # Rocksmith2014.NET documents 40/80/120 as supported strength values.
        # GP/MusicXML import currently carries presence but not calibrated strength,
        # so use the neutral medium value rather than pretending to know more.
        attributes["vibrato"] = "80"
    return attributes


def _text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = str(value)
    return child


def _base_arrangement_properties() -> dict[str, str]:
    return {name: "0" for name in _ARRANGEMENT_PROPERTY_NAMES}


def _arrangement_properties(mapping: BassMapping) -> dict[str, str]:
    properties = _base_arrangement_properties()
    properties["represent"] = "1"
    properties["pathBass"] = "1"
    properties["standardTuning"] = (
        "1" if mapping.tuning.open_midi == _STANDARD_BASS_OPEN_MIDI else "0"
    )
    properties["sustain"] = "1" if any(note.duration > 0.05 for note in mapping.notes) else "0"
    techniques = {technique for note in mapping.notes for technique in note.techniques}
    properties["palmMutes"] = "1" if "palm_mute" in techniques else "0"
    properties["harmonics"] = "1" if "harmonic" in techniques else "0"
    properties["tremolo"] = "1" if "tremolo_picking" in techniques else "0"
    properties["vibrato"] = "1" if "vibrato" in techniques else "0"
    return properties


def _guitar_arrangement_properties(chart: GuitarAuthoringChart) -> dict[str, str]:
    properties = _base_arrangement_properties()
    properties["represent"] = "1"
    properties["pathLead"] = "1" if chart.arrangement == "lead" else "0"
    properties["pathRhythm"] = "1" if chart.arrangement == "rhythm" else "0"
    properties["standardTuning"] = "1" if chart.tuning_midi == _STANDARD_GUITAR_OPEN_MIDI else "0"
    all_notes = [*chart.single_notes, *(note for chord in chart.chords for note in chord.notes)]
    techniques = {technique for note in all_notes for technique in note.techniques}
    properties["sustain"] = "1" if any(note.duration_seconds > 0.05 for note in all_notes) else "0"
    properties["doubleStops"] = "1" if any(len(chord.notes) == 2 for chord in chart.chords) else "0"
    properties["palmMutes"] = "1" if "palm_mute" in techniques else "0"
    properties["harmonics"] = "1" if "harmonic" in techniques else "0"
    properties["tremolo"] = "1" if "tremolo_picking" in techniques else "0"
    properties["vibrato"] = "1" if "vibrato" in techniques else "0"
    return properties


def _build_common_song_header(
    manifest: ProjectManifest,
    tempo_map: TempoMap,
    *,
    arrangement_name: str,
    tuning_offsets: tuple[int, int, int, int, int, int],
    arrangement_properties: dict[str, str],
) -> ET.Element:
    if not manifest.artist or not manifest.artist.strip():
        raise ValueError("Rocksmith authoring export requires explicit artist metadata")
    if not tempo_map.beats:
        raise ValueError("Cannot export Rocksmith XML without beats")

    root = ET.Element("song", {"version": "7"})
    _text(root, "title", manifest.title)
    _text(root, "arrangement", arrangement_name)
    _text(root, "part", 1)
    _text(root, "offset", "0.000")
    _text(root, "centOffset", 0)
    _text(root, "songLength", f"{manifest.source_metadata.duration_seconds:.3f}")
    _text(root, "startBeat", f"{tempo_map.beats[0].time:.3f}")
    average_bpm = mean(beat.bpm for beat in tempo_map.beats)
    _text(root, "averageTempo", f"{average_bpm:.3f}")

    ET.SubElement(
        root,
        "tuning",
        {f"string{index}": str(offset) for index, offset in enumerate(tuning_offsets)},
    )
    _text(root, "capo", 0)
    artist = manifest.artist.strip()
    _text(root, "artistName", artist)
    _text(root, "artistNameSort", artist)
    _text(root, "albumName", "")
    _text(root, "albumYear", "")
    _text(root, "crowdSpeed", 1)
    ET.SubElement(root, "arrangementProperties", arrangement_properties)

    phrases = ET.SubElement(root, "phrases", {"count": "1"})
    ET.SubElement(phrases, "phrase", {"name": "song", "maxDifficulty": "0"})
    phrase_iterations = ET.SubElement(root, "phraseIterations", {"count": "1"})
    ET.SubElement(
        phrase_iterations,
        "phraseIteration",
        {"time": f"{tempo_map.beats[0].time:.3f}", "phraseId": "0"},
    )

    ET.SubElement(root, "newLinkedDiffs", {"count": "0"})
    ET.SubElement(root, "linkedDiffs", {"count": "0"})
    ET.SubElement(root, "phraseProperties", {"count": "0"})

    ebeats = ET.SubElement(root, "ebeats", {"count": str(len(tempo_map.beats))})
    for beat in tempo_map.beats:
        attributes = {"time": f"{beat.time:.3f}"}
        if beat.is_downbeat or beat.beat == 1:
            attributes["measure"] = str(beat.measure)
        ET.SubElement(ebeats, "ebeat", attributes)

    sections = ET.SubElement(root, "sections", {"count": "1"})
    ET.SubElement(
        sections,
        "section",
        {"name": "song", "number": "1", "startTime": f"{tempo_map.beats[0].time:.3f}"},
    )

    events = ET.SubElement(root, "events", {"count": "1"})
    ET.SubElement(
        events,
        "event",
        {
            "time": f"{tempo_map.beats[0].time:.3f}",
            "code": f"TS:{tempo_map.time_signature_numerator}/{tempo_map.time_signature_denominator}",
        },
    )

    transcription_track = ET.SubElement(root, "transcriptionTrack", {"difficulty": "-1"})
    for tag in ("notes", "chords", "anchors", "handShapes"):
        ET.SubElement(transcription_track, tag, {"count": "0"})
    return root


def build_rocksmith_bass_xml(
    manifest: ProjectManifest,
    tempo_map: TempoMap,
    mapping: BassMapping,
) -> ET.Element:
    if not mapping.notes:
        raise ValueError("Cannot export Rocksmith XML without mapped bass notes")
    if any(not note.mapped for note in mapping.notes):
        raise ValueError("Cannot export Rocksmith XML while bass notes remain unmapped")

    root = _build_common_song_header(
        manifest,
        tempo_map,
        arrangement_name="Bass",
        tuning_offsets=rocksmith_tuning_offsets(mapping),
        arrangement_properties=_arrangement_properties(mapping),
    )

    ET.SubElement(root, "chordTemplates", {"count": "0"})
    ET.SubElement(root, "fretHandMuteTemplates", {"count": "0"})

    levels = ET.SubElement(root, "levels", {"count": "1"})
    level = ET.SubElement(levels, "level", {"difficulty": "0"})
    notes_element = ET.SubElement(level, "notes", {"count": str(len(mapping.notes))})
    for note in mapping.notes:
        assert note.string is not None and note.fret is not None
        attributes = {
            "time": f"{note.start:.3f}",
            "string": str(note.string),
            "fret": str(note.fret),
        }
        if note.duration > 0.01:
            attributes["sustain"] = f"{note.duration:.3f}"
        attributes.update(_technique_attributes(note))
        ET.SubElement(notes_element, "note", attributes)

    ET.SubElement(level, "chords", {"count": "0"})
    ET.SubElement(level, "fretHandMutes", {"count": "0"})
    ET.SubElement(level, "anchors", {"count": "0"})
    ET.SubElement(level, "handShapes", {"count": "0"})
    return root


def build_rocksmith_guitar_xml(
    manifest: ProjectManifest,
    tempo_map: TempoMap,
    chart: GuitarAuthoringChart,
) -> ET.Element:
    """Build a single-level Rocksmith 2014 Lead or Rhythm arrangement XML."""
    if chart.arrangement not in {"lead", "rhythm"}:
        raise ValueError("Guitar XML export only supports lead or rhythm arrangements")
    if chart.unresolved_notes:
        raise ValueError("Cannot export Rocksmith guitar XML while unresolved notes remain")
    if not chart.single_notes and not chart.chords:
        raise ValueError("Cannot export Rocksmith guitar XML without notes or chords")

    arrangement_name = "Lead" if chart.arrangement == "lead" else "Rhythm"
    root = _build_common_song_header(
        manifest,
        tempo_map,
        arrangement_name=arrangement_name,
        tuning_offsets=rocksmith_guitar_tuning_offsets(chart),
        arrangement_properties=_guitar_arrangement_properties(chart),
    )

    chord_by_id = {chord.chord_id: chord for chord in chart.chords}
    chord_templates = ET.SubElement(root, "chordTemplates", {"count": str(len(chord_by_id))})
    for chord_id in sorted(chord_by_id):
        chord = chord_by_id[chord_id]
        attributes = {
            "chordName": "",
            "displayName": "",
            **{f"fret{string_index}": str(fret) for string_index, fret in enumerate(chord.shape)},
            # Fingering is intentionally unknown at this stage. Rocksmith XML uses -1
            # for an unused/unknown finger rather than forcing a fabricated fingering.
            **{f"finger{string_index}": "-1" for string_index in range(6)},
        }
        ET.SubElement(chord_templates, "chordTemplate", attributes)
    ET.SubElement(root, "fretHandMuteTemplates", {"count": "0"})

    levels = ET.SubElement(root, "levels", {"count": "1"})
    level = ET.SubElement(levels, "level", {"difficulty": "0"})

    notes_element = ET.SubElement(level, "notes", {"count": str(len(chart.single_notes))})
    for note in chart.single_notes:
        attributes = {
            "time": f"{note.start_seconds:.3f}",
            "string": str(note.string_index),
            "fret": str(note.fret),
        }
        if note.duration_seconds > 0.01:
            attributes["sustain"] = f"{note.duration_seconds:.3f}"
        attributes.update(_technique_attributes(note))
        ET.SubElement(notes_element, "note", attributes)

    chords_element = ET.SubElement(level, "chords", {"count": str(len(chart.chords))})
    for chord in chart.chords:
        chord_attributes = {
            "time": f"{chord.start_seconds:.3f}",
            "chordId": str(chord.chord_id),
        }
        if chord.sustain_seconds > 0.01:
            chord_attributes["sustain"] = f"{chord.sustain_seconds:.3f}"
        chord_element = ET.SubElement(chords_element, "chord", chord_attributes)
        for note in sorted(chord.notes, key=lambda item: item.string_index):
            note_attributes = {
                "time": f"{note.start_seconds:.3f}",
                "string": str(note.string_index),
                "fret": str(note.fret),
            }
            if note.duration_seconds > 0.01:
                note_attributes["sustain"] = f"{note.duration_seconds:.3f}"
            note_attributes.update(_technique_attributes(note))
            ET.SubElement(chord_element, "chordNote", note_attributes)

    ET.SubElement(level, "fretHandMutes", {"count": "0"})
    ET.SubElement(level, "anchors", {"count": "0"})
    ET.SubElement(level, "handShapes", {"count": "0"})
    return root


def write_rocksmith_xml(root: ET.Element, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(destination, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
