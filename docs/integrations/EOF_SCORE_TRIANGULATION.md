# EOF / alternate-score triangulation

The project can compare a private alternate Guitar Pro 3/4/5 score against the currently registered score without changing project authority.

## Windows workflow

Open Song Workspace and use **Timeline → Editor on Fire reference → Compare alternate GP…**. Select a local `.gp3`, `.gp4`, or `.gp5` file. The program reparses both scores with the normal Guitar Pro importer and writes `review/eof_score_triangulation_report.json`.

The report compares Bass, Lead, and Rhythm independently where credible tracks can be selected. It records track identity, tuning, note counts, first playable source time, tempo/time-signature structure, and the first deterministic event prefix for MIDI/string/fret coordinates and source-relative onset timing.

The alternate score stays at its original local path. It is not copied into the repository or promoted to canonical source state.

## CLI

```powershell
cdlc-eof "C:\Path\To\project" --compare-score "C:\Private\alternate-score.gp5"
```

## Relationship to EOF checks

This layer answers a different question from EOF recording-clock parity:

- **GP ↔ GP triangulation** asks whether two structured score sources agree before recording alignment.
- **EOF source compatibility** asks whether our Guitar Pro interpretation agrees with independently observed EOF interpretation.
- **EOF recording-clock parity** asks whether the interpreted source is mapped to the correct place in the actual recording.

Together these checks localize failures much more precisely than a single end-to-end pass.

## Safety and provenance

The report stores SHA-256 identities for both score files and fails closed when either referenced file changes or disappears. The alternate score is advisory evidence only and cannot silently replace the registered score, mappings, shared timeline, reviewed notes, validation state, or Rocksmith export state.
