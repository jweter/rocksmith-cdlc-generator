from __future__ import annotations

import json
from pathlib import Path

import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.midi_import import MidiImportError, import_midi, import_project_midi
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceTrustClass


def _write_multitrack_midi(path: Path) -> Path:
    midi = MidiFile(type=1, ticks_per_beat=480)

    conductor = MidiTrack()
    conductor.append(MetaMessage("track_name", name="Conductor", time=0))
    conductor.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    conductor.append(MetaMessage("set_tempo", tempo=500_000, time=0))
    conductor.append(MetaMessage("set_tempo", tempo=1_000_000, time=480))
    midi.tracks.append(conductor)

    lead = MidiTrack()
    lead.append(MetaMessage("track_name", name="Lead Guitar", time=0))
    lead.append(Message("program_change", program=29, channel=0, time=0))
    lead.append(Message("note_on", note=64, velocity=90, channel=0, time=0))
    lead.append(Message("note_off", note=64, velocity=0, channel=0, time=480))
    midi.tracks.append(lead)

    bass = MidiTrack()
    bass.append(MetaMessage("track_name", name="Bass", time=0))
    bass.append(Message("program_change", program=33, channel=1, time=0))
    bass.append(Message("note_on", note=28, velocity=100, channel=1, time=0))
    bass.append(Message("note_off", note=28, velocity=0, channel=1, time=480))
    bass.append(Message("note_on", note=33, velocity=100, channel=1, time=0))
    bass.append(Message("note_off", note=33, velocity=0, channel=1, time=480))
    midi.tracks.append(bass)

    rhythm = MidiTrack()
    rhythm.append(MetaMessage("track_name", name="Rhythm Guitar", time=0))
    rhythm.append(Message("program_change", program=27, channel=2, time=0))
    rhythm.append(Message("note_on", note=52, velocity=90, channel=2, time=0))
    rhythm.append(Message("note_on", note=55, velocity=90, channel=2, time=0))
    rhythm.append(Message("note_off", note=52, velocity=0, channel=2, time=480))
    rhythm.append(Message("note_off", note=55, velocity=0, channel=2, time=0))
    midi.tracks.append(rhythm)

    midi.save(path)
    return path


def test_midi_import_selects_bass_and_preserves_tempo_timing(tmp_path: Path) -> None:
    midi_path = _write_multitrack_midi(tmp_path / "song.mid")

    imported = import_midi(midi_path)

    assert imported.provenance.source_type == "midi"
    assert imported.provenance.source_sha256 == sha256_file(midi_path)
    assert imported.ticks_per_beat == 480
    assert [round(event.bpm) for event in imported.tempo_events] == [120, 60]
    assert len(imported.time_signatures) == 1

    track = imported.tracks[0]
    assert track.instrument == "bass"
    assert track.source_track_index == 2
    assert track.name == "Bass"
    assert track.program_numbers == [33]
    assert track.channel_numbers == [1]
    assert [note.midi for note in track.notes] == [28, 33]
    assert [note.note_name for note in track.notes] == ["E1", "A1"]
    assert track.notes[0].start_seconds == pytest.approx(0.0)
    assert track.notes[0].duration_seconds == pytest.approx(0.5)
    assert track.notes[1].start_seconds == pytest.approx(0.5)
    assert track.notes[1].duration_seconds == pytest.approx(1.0)
    assert all(note.import_confidence == 1.0 for note in track.notes)
    assert all(note.trust_class == SourceTrustClass.symbolic_unverified for note in track.notes)


def test_midi_import_selects_lead_and_rhythm_tracks(tmp_path: Path) -> None:
    midi_path = _write_multitrack_midi(tmp_path / "song.mid")
    lead = import_midi(midi_path, instrument="lead").tracks[0]
    rhythm = import_midi(midi_path, instrument="rhythm").tracks[0]

    assert lead.instrument == "lead"
    assert lead.source_track_index == 1
    assert lead.name == "Lead Guitar"
    assert [note.midi for note in lead.notes] == [64]

    assert rhythm.instrument == "rhythm"
    assert rhythm.source_track_index == 3
    assert rhythm.name == "Rhythm Guitar"
    assert [note.midi for note in rhythm.notes] == [52, 55]
    assert rhythm.notes[0].start_seconds == rhythm.notes[1].start_seconds


def test_midi_import_rejects_ambiguous_track_selection(tmp_path: Path) -> None:
    midi = MidiFile(type=1, ticks_per_beat=480)
    for pitch in (40, 41):
        track = MidiTrack()
        track.append(Message("note_on", note=pitch, velocity=80, channel=0, time=0))
        track.append(Message("note_off", note=pitch, velocity=0, channel=0, time=480))
        midi.tracks.append(track)
    path = tmp_path / "ambiguous.mid"
    midi.save(path)

    with pytest.raises(MidiImportError, match="ambiguous"):
        import_midi(path)

    imported = import_midi(path, track_index=1)
    assert imported.tracks[0].source_track_index == 1
    assert imported.tracks[0].notes[0].midi == 41


def test_midi_import_rejects_unclosed_notes(tmp_path: Path) -> None:
    midi = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="Bass", time=0))
    track.append(Message("note_on", note=28, velocity=100, channel=0, time=0))
    midi.tracks.append(track)
    path = tmp_path / "broken.mid"
    midi.save(path)

    with pytest.raises(MidiImportError, match="unclosed"):
        import_midi(path)


def test_project_midi_import_writes_versioned_neutral_source(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    midi_path = _write_multitrack_midi(tmp_path / "song.mid")

    output = import_project_midi(project, midi_path)

    assert output.parent == project / "sources" / "imported"
    assert output.name.startswith("song-")
    payload = ImportedSource.read_json(output)
    assert payload.schema_version == 1
    assert payload.provenance.source_filename == "song.mid"
    assert json.loads(output.read_text(encoding="utf-8"))["tracks"][0]["instrument"] == "bass"


def test_project_midi_guitar_artifact_is_role_named(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    midi_path = _write_multitrack_midi(tmp_path / "song.mid")

    output = import_project_midi(project, midi_path, instrument="lead")
    assert "-lead-" in output.name
    assert ImportedSource.read_json(output).tracks[0].instrument == "lead"
