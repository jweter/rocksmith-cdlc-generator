# Owner-approved roadmap direction — 2026-10-25

Status: proposed roadmap addendum for review, not an accepted implementation or permission to execute.

This records explicit owner decisions. Reconcile with the authoritative local roadmap, AGENTS.md, active claims, dirty worktrees, and newer accepted work before implementation. Existing safety, provenance, testing, product-reality, controller authorization, and worker lease gates remain mandatory. Do not treat GitHub main as newer than the authoritative local version.

## First usable product milestone
- Import a song, generate a playable Rocksmith CDLC arrangement, validate it, and export a game-compatible artifact.
- Prioritize the complete user workflow while retaining measurable musical correctness and valid fingering/tempo/notes as acceptance requirements.
- No claim of playability from synthetic/unit checks alone: validate a real export and in-game Product Reality where available.

## Next slices
1. Audit current import-to-export chain and identify first broken real-song seam.
2. Repair the smallest end-to-end seam with regression tests and provenance.
3. Validate an exported playable arrangement and document accuracy limitations.
