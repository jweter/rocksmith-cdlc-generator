# Score role composition contract

Issue #232 requires multiple complete-score tracks to contribute to one Rocksmith Bass, Lead, or Rhythm arrangement without silently losing Clean, Solo, alternate Lead, or alternate Rhythm material.

`score_role_composition.py` introduces the first authority-safe contract for that work. A composition selection is an ordered list of source-track indexes for one Rocksmith role, bound to the exact registered score SHA-256 and format. The existing human-confirmed one-track mapping remains the primary authority during this incremental transition: the first track in every composition must be that exact confirmed primary. Additional tracks are explicit additions only; names, importer confidence, and coverage warnings never add them automatically.

Validation fails closed if the score provenance changes, a selected track no longer exists, a role lacks a human-confirmed primary mapping, the confirmed primary is reordered behind an added track, a role is duplicated, or a source track is duplicated within one role.

This slice deliberately does **not** persist composition choices in the project UI, merge note streams, define section scopes, resolve overlapping/conflicting notes, change fan-out, alter timing, write Rocksmith XML, package CDLC, or grant source/timing/fingering/chord/technique/tone/validation authority. Those downstream steps must bind to the full confirmed source-track set and keep conflicts explicit and reviewable.

No live Rocksmith installation or NoCableLauncher state is touched. No commercial audio/DLC, private CFSM exports, Ubisoft-derived content, PSARC packages, or generated private project data are committed.
