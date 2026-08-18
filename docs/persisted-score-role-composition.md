# Persisted score role composition

Issue #232 requires explicit human-confirmed composition of multiple complete-score tracks into one Rocksmith Bass, Lead, or Rhythm arrangement. The preceding composition contract established the ordered authority model; this slice makes that intent durable inside the project without yet consuming it downstream.

`score_role_composition_review.py` persists the current plan at `review/score_role_composition.json`. Reads and writes share the score-mapping transaction so a mapping confirmation cannot race a composition update. Every read revalidates the registered score bytes, score SHA-256/format, selected track identities, and the current human-confirmed primary mapping for each composed role.

A later mapping change therefore makes the old persisted plan fail closed rather than silently remaining authoritative. The user may explicitly write a new plan after the new primary mapping is confirmed; the new plan is then validated from the current score state before atomically replacing the prior file. Invalid writes do not damage the last valid persisted plan.

This artifact records composition intent only. It does not auto-assign extra tracks, merge note streams, define section scopes, resolve overlaps/conflicts, change score fan-out, alter timing, accept source/fingering/chord/technique/tone decisions, write Rocksmith XML, package CDLC, modify the live Rocksmith installation, or interact with NoCableLauncher. Downstream work must continue to preserve every included source track's provenance and keep overlapping/conflicting material explicit and reviewable.

The persisted review artifact is project-local generated/private state and follows the existing project workspace privacy boundary; no commercial audio/tabs/DLC, private CFSM exports, Ubisoft-derived content, PSARC packages, or generated private project evidence are committed.
