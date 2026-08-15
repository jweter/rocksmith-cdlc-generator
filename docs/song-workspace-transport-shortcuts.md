# Song Workspace keyboard transport

The packaged Song Workspace supports a small set of review-oriented keyboard transport controls after playback is available:

- `Space` or `K`: play/pause.
- `J`: seek backward 5 seconds.
- `L`: seek forward 5 seconds.
- `Home`: seek to the beginning of the song.
- `End`: seek to the end of the song.

The shortcuts are intentionally conservative. They are bound only to the Song Workspace window, not globally. Transport dispatch is suspended while focus is in text-entry, text, combobox, or spinbox controls, and Ctrl/Alt-modified key chords are left untouched for application/editor commands.

These controls affect local preview position only. They do not accept timing, notes, positions, fingering, techniques, chord identity, tones, score mappings, source rights, validation findings, packaging, or installation state. All existing human review and provenance gates remain authoritative.
