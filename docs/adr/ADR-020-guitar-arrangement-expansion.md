# ADR-020: Lead and Rhythm guitar arrangement expansion

## Status
Accepted for Milestones 9-10.

## Context
The project was intentionally developed Bass-first. The neutral symbolic-source contract, timing alignment, provenance, and Guitar Pro parser are already capable of representing six-string note events, including simultaneous notes, exact string/fret positions, tuning, and imported techniques. The current Guitar Pro adapter, however, hard-coded Bass track selection and labeled every imported track as `bass`.

Rocksmith 2014's playable guitar arrangements are not interchangeable. Lead and Rhythm have distinct arrangement identities and DLC Builder route metadata, and guitar sources must preserve six-string tuning and polyphony so later export can construct chords instead of flattening them into a Bass-style monophonic chart.

## Decision
1. `bass`, `lead`, and `rhythm` are first-class arrangement roles.
2. Guitar Pro import accepts an arrangement role and selects a matching track using deterministic role-specific heuristics. Explicit track selection always overrides heuristics.
3. Bass selection remains backward-compatible and retains its existing Bass-specific scoring.
4. Lead/Rhythm automatic selection rejects obvious Bass tracks, favors six-string guitar tracks and General MIDI guitar programs, and gives the strongest evidence to explicit `Lead`, `Solo`, `Rhythm`, and chord-oriented track names.
5. Imported six-string tuning is normalized low-string-first, matching the neutral source model and later Rocksmith string numbering.
6. Simultaneous notes are preserved as independent source note events with identical onset time. Chord identity/shape is derived later at the arrangement-authoring layer; import must not discard polyphony.
7. Structured notation is the initial high-confidence path for guitar arrangements. The existing monophonic pYIN Bass transcription is not relabeled or reused as a polyphonic guitar transcription engine.
8. Lead/Rhythm notes remain `symbolic_unverified` until alignment/reconciliation or deliberate human confirmation provides stronger evidence.

## Follow-on work
- Expose `--instrument bass|lead|rhythm` on Guitar Pro and MusicXML import commands.
- Generalize MusicXML part selection for Lead/Rhythm.
- Add a six-string arrangement model that groups simultaneous source notes into Rocksmith chord events while preserving single-note techniques.
- Export correct Rocksmith Lead/Rhythm XML arrangement identity and DLC Builder route masks.
- Generalize validation/review artifacts per arrangement.
- Add optional guitar audio evidence later; do not block structured-source guitar authoring on a premature polyphonic transcription model.

## Consequences
This allows guitar arrangements to reuse the mature provenance/alignment/import infrastructure while keeping Bass behavior stable. It also makes chord handling an explicit authoring concern rather than silently flattening polyphonic notation during import.