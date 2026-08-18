# Unmapped playable score-track coverage

Issue #232 exists because a complete Guitar Pro/MusicXML score can contain more playable guitar material than the current one-track-per-role Bass/Lead/Rhythm mapping contract can represent. A normal example is a score with Rhythm, Lead, Clean Guitar, Solo, and Bass tracks: choosing one Lead and one Rhythm track can otherwise make the remaining guitar parts disappear from the operational workflow even though they are still present in the registered score.

This slice adds a read-only mapping coverage model. It reports the current Lead/Rhythm/Bass mapping references and separately lists pitched score tracks that the score inventory already classified as `guitar` or `bass` but that no role mapping references. The `cdlc-score-map PROJECT coverage` command exposes the same JSON view for diagnostics and future Song Workspace integration.

The coverage model is intentionally conservative. It does not infer that an extra guitar track belongs to Lead or Rhythm, does not merge notes, does not alter score mappings, and does not make an unconfirmed mapping authoritative. A percussion or otherwise unclassified track is not promoted merely because it has low notes, string-like metadata, or a suggestive name; the model relies only on the existing score inventory's explicit playable instrument hint. This preserves the percussion-rejection boundary established by the Product Reality corrections.

The purpose of this first #232 slice is loss visibility, not multi-track composition authority. A following slice can surface the coverage warning in Song Workspace and then add an explicit human-confirmed ordered/section-scoped composition contract. Until that exists, fan-out remains one source track per role and all existing provenance, timing, chord, technique, source-acceptance, validation, packaging, live Rocksmith, and NoCableLauncher boundaries remain unchanged.

No commercial audio/tabs/DLC, private CFSM exports, Ubisoft-derived content, PSARC packages, or generated private project data are committed by this feature.
