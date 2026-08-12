# Read-only Song Preview Data Snapshot

The first Song Preview & Timing Editor consumer is intentionally a data-layer slice, not a GUI and not an editor yet.

It reads one trusted MusicXML arrangement manifest and projects its normalized arrangement artifacts into a GUI-friendly `SongPreviewSnapshot`.

## Usage

```text
py -3.12 scripts/preview_musicxml_arrangements.py PROJECT PROJECT/sources/imported/musicxml-arrangements-<sha-prefix>.json
```

The snapshot exposes:

- source filename and SHA-256;
- one canonical beat grid, tempo-event list, and time-signature list;
- Lead/Rhythm/Bass arrangement metadata from the trusted manifest;
- source-track name and tuning;
- normalized note onset, duration, MIDI pitch/note name, string/fret, techniques, import confidence, trust class, and review-required state;
- imported warnings.

This is a read-only projection. It does not modify note timing, beat timing, source files, imported artifacts, manifests, or Rocksmith files.

## Integrity gates

The loader fails closed when:

- the manifest or an arrangement JSON escapes the project directory;
- a referenced file is missing;
- the manifest contains duplicate arrangement roles or reuses one source part for multiple roles;
- normalized source provenance does not match the manifest source filename/SHA-256;
- normalized track role or source-part index disagrees with the manifest;
- tuning or pitched-note count disagrees with the manifest;
- Lead/Rhythm/Bass artifacts do not share the same beat/tempo/time-signature timebase.

These checks let the future desktop workspace treat `SongPreviewSnapshot` as a stable display model instead of re-implementing source validation in Qt widgets.

## Next intended layers

Later slices can build on this model to add project-level manifest discovery, waveform/audio references, playback transport, variable-tempo click, and eventually non-destructive timing edits. Those concerns are intentionally outside this slice.
