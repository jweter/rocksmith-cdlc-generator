# Printed-score-only project bootstrap

Status: implementation slice

This closes a practical gap in the photographed-score proof of concept: the Windows desktop previously required a normal audio-backed `ProjectManifest` before a project could be opened, while private printed-score registration could create a directory without that desktop manifest.

## New score-only project path

The Windows **Printed score practice** section now starts with **New Score Project…**.

The setup flow asks for:

1. the public-safe printed-score YAML manifest;
2. the local folder containing the private page photographs;
3. the parent folder where the Rocksmith project should be created;
4. the movement/section to practice.

Project creation then runs through the existing background worker and:

- validates the YAML;
- creates a normal desktop-openable project directory;
- privately copies and verifies every expected page image;
- enforces every expected page SHA-256;
- writes the registered private bundle manifest;
- rolls the entire project back if any page is missing, corrupt, or has the wrong hash;
- opens the new project automatically when registration succeeds.

## Legacy shell compatibility

The current `ProjectManifest` model was originally audio-first. Until source modes are generalized across every mature subsystem, a score-only project contains a generated one-second silent WAV as a compatibility scaffold.

That WAV is explicitly **not musical authority**:

- recognition never derives notes or timing from it;
- reviewed notation remains the score authority;
- the practice tempo map and count-in/click are generated later from the reviewed notation fixture;
- the desktop disables the normal **Continue Automatically** recording workflow for a detected printed-score project.

This keeps older project/readiness code from trying to interpret a YAML/JSON file as audio while avoiding a large unrelated source-mode migration during the first proof of concept.

## Printed-score guided progress

When a registered printed-score project is open, the normal song-workflow progress card is replaced with printed-score-specific guidance:

- 15% — private score registered → **Recognize**;
- 45% — candidates exist → **Review**;
- 75% — reviewed fixture exists → **Build Practice**;
- 100% — validated Bass XML + click WAV exist.

The normal recording **Continue Automatically** control is disabled for these projects to prevent accidental transcription/normalization work on the compatibility scaffold.

## CLI

A matching bootstrap command is available:

```powershell
cdlc-score-project --manifest benchmarks/private_reference_sets/bwv1007_bass_dropd.yaml --source-dir <PRIVATE_PHOTO_FOLDER> --projects-root projects --movement prelude
```

`--list-movements` prints the movement IDs and page ranges without creating a project.

## BWV1007 acceptance target

For the current private Bach source the intended laptop path is now:

```text
New Score Project
  → choose bwv1007_bass_dropd.yaml
  → choose folder containing IMG_4388.jpeg ... IMG_4402.jpeg
  → movement = prelude
  → Recognize page 2 (5 systems, first 8 measures)
  → Review/correct every measure
  → export reviewed fixture at chosen BPM
  → Build Practice (2-measure count-in)
  → validate generated click + Bass Rocksmith XML
```

The next hard gate is the first real laptop run of that exact path.
