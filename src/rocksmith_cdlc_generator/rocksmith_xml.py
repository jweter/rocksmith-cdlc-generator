from __future__ import annotations

from pathlib import Path
from statistics import mean
from xml.etree import ElementTree as ET

from .beats import TempoMap
from .fret_mapping import BassMapping
from .models import ProjectManifest

_STANDARD_BASS_OPEN_MIDI = (28, 33, 38, 43)

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


def rocksmith_tuning_offsets(mapping: BassMapping) -> tuple[int, int, int, int, int, int]:
    """Convert absolute open-string MIDI pitches to Rocksmith semitone offsets."""
    bass_offsets = tuple(
        actual - standard
        for actual, standard in zip(mapping.tuning.open_midi, _STANDARD_BASS_OPEN_MIDI)
    )
    return (*bass_offsets, 0, 0)


def _text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = str(value)
    return child


def _arrangement_properties(mapping: BassMapping) -> dict[str, str]:
    properties = {name: "0" for name in _ARRANGEMENT_PROPERTY_NAMES}
    properties["represent"] = "1"
    properties["pathBass"] = "1"
    properties["standardTuning"] = (
        "1" if mapping.tuning.open_midi == _STANDARD_BASS_OPEN_MIDI else "0"
    )
    properties["sustain"] = "1" if any(note.duration > 0.05 for note in mapping.notes) else "0"
    return properties


def build_rocksmith_bass_xml(
    manifest: ProjectManifest,
    tempo_map: TempoMap,
    mapping: BassMapping,
) -> ET.Element:
    if not manifest.artist or not manifest.artist.strip():
        raise ValueError("Rocksmith authoring export requires explicit artist metadata")
    if not tempo_map.beats:
        raise ValueError("Cannot export Rocksmith XML without beats")
    if not mapping.notes:
        raise ValueError("Cannot export Rocksmith XML without mapped bass notes")
    if any(not note.mapped for note in mapping.notes):
        raise ValueError("Cannot export Rocksmith XML while bass notes remain unmapped")

    root = ET.Element("song", {"version": "7"})
    _text(root, "title", manifest.title)
    _text(root, "arrangement", "Bass")
    _text(root, "part", 1)
    _text(root, "offset", "0.000")
    _text(root, "centOffset", 0)
    _text(root, "songLength", f"{manifest.source_metadata.duration_seconds:.3f}")
    _text(root, "startBeat", f"{tempo_map.beats[0].time:.3f}")
    average_bpm = mean(beat.bpm for beat in tempo_map.beats)
    _text(root, "averageTempo", f"{average_bpm:.3f}")

    offsets = rocksmith_tuning_offsets(mapping)
    ET.SubElement(
        root,
        "tuning",
        {f"string{index}": str(offset) for index, offset in enumerate(offsets)},
    )
    _text(root, "capo", 0)
    artist = manifest.artist.strip()
    _text(root, "artistName", artist)
    _text(root, "artistNameSort", artist)
    _text(root, "albumName", "")
    _text(root, "albumYear", "")
    _text(root, "crowdSpeed", 1)
    ET.SubElement(root, "arrangementProperties", _arrangement_properties(mapping))

    phrases = ET.SubElement(root, "phrases", {"count": "1"})
    ET.SubElement(phrases, "phrase", {"name": "song", "maxDifficulty": "0"})
    phrase_iterations = ET.SubElement(root, "phraseIterations", {"count": "1"})
    ET.SubElement(
        phrase_iterations,
        "phraseIteration",
        {"time": f"{tempo_map.beats[0].time:.3f}", "phraseId": "0"},
    )

    for tag in ("newLinkedDiffs", "linkedDiffs", "phraseProperties", "chordTemplates", "fretHandMuteTemplates"):
        ET.SubElement(root, tag, {"count": "0"})

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
        ET.SubElement(notes_element, "note", attributes)

    ET.SubElement(level, "chords", {"count": "0"})
    ET.SubElement(level, "fretHandMutes", {"count": "0"})
    ET.SubElement(level, "anchors", {"count": "0"})
    ET.SubElement(level, "handShapes", {"count": "0"})
    return root


def write_rocksmith_xml(root: ET.Element, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(destination, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
