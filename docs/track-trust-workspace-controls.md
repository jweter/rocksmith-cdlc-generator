# Track trust Song Workspace controller

Issue #268 now has three distinct layers for whole-track source trust: the provenance-bound acceptance artifact, the read-only per-track eligibility/status model, and this UI-ready controller layer.

`track_trust_workspace_controls.py` converts the current status model into deterministic control state for Bass, Lead, and Rhythm. Each control exposes the current review state (`unreviewed`, `current`, or `stale`), the exact acceptance scope, a state-specific button label, whether the action may be offered, and any blocker text. The controller also provides one explicit action entry point that refuses disabled actions, invokes the existing provenance-bound acceptance write, and returns freshly inspected control state.

The accepted scope remains deliberately narrow: `imported_note_identity_and_positions`. A whole-track acceptance means the user has accepted the exact current imported symbolic note identities and their concrete pitch-consistent string/fret positions for that source track. It does not accept timing, ties or other techniques, chord identity/fingering, source rights, score-role mapping, validation results, tones, package readiness, or any live-game state.

The controller precheck is user-facing guidance, not authority. `record_track_source_trust_acceptance` still performs the authoritative write-time validation against the registered score, human-confirmed mapping, current fan-out manifest and content hashes, tuning, positions, and pitch consistency. Stale evidence therefore cannot become current merely because a UI button was enabled earlier.

This slice intentionally stops before Tk widget integration. The next desktop slice can bind these deterministic controls into Arrangement Preview without duplicating acceptance logic or weakening fail-closed behavior.

Safety boundaries remain unchanged: no live Rocksmith installation or NoCableLauncher modification; no commercial audio/tabs/DLC, private CFSM exports, generated private project evidence, Ubisoft-derived content, or PSARC packages are committed; uncertain musical, tone, source-rights, and independent event-review decisions remain human-controlled.
