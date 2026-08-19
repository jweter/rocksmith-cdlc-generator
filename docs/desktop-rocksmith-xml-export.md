# Desktop Rocksmith XML export

The packaged Windows product exposes **Workspace → Rocksmith XML Export…** for Bass, Lead, and Rhythm.

## Product behavior

Each arrangement is exported independently through the existing deterministic authoring exporter. Bass continues to use `require_packaging_ready()`. Lead and Rhythm continue to run their arrangement validation and block export when hard failures remain. The desktop layer does not duplicate or replace those gates.

The export window intentionally has no one-click `Export All` action. Independent export keeps a blocked Lead or Rhythm arrangement from being obscured by a partially successful batch and makes the authoritative failure visible for the arrangement that needs review.

Export work runs through the desktop background-operation boundary so XML generation and validation do not intentionally block Tk while the engine is working. On success the window reports the exact project-local XML path and refreshes the Song Workspace.

Existing XML is never considered current merely because a file exists. Current validation/XML readiness remains a projection of upstream review authority in the Song Workspace Validation tab, and every requested export re-enters the engine's validation gate.

## Reviewed score-anchor timing routing

Once a project has promoted score-anchor timing (`analysis/reviewed_score_timing.json`, written by the Song Workspace timing-review "promote" action), `authoring_export.py` reads notes, positions, and timing for that arrangement through `reviewed_rocksmith_xml_render.py` instead of the older `charts/<role>_source.json` mapping/chart file. This makes the exported XML reflect the exact human-reviewed sparse-anchor-refit timing rather than the earlier uncorrected mapping.

Projects that have never promoted reviewed score timing are unaffected and continue to export from `charts/bass_mapped.json` / `charts/<role>_source.json` exactly as before.

The routing decision is fail-closed, not best-effort: once `analysis/reviewed_score_timing.json` exists, any failure building the reviewed input for that arrangement (stale promotion, an unconfirmed score mapping for that role, a stale fan-out, or an unsupported technique) is raised to the caller. Export never silently falls back to the older unreviewed chart path once a project has opted into reviewed timing, so a broken reviewed state cannot be masked by quietly exporting different, lower-trust data. The pre-existing Bass/guitar packaging and arrangement validation gates still run first and are unchanged by which timing source the XML is rendered from.

## Safety and authority boundary

This surface does not accept or alter source rights, score mappings, shared timing, notes, physical positions, fingering, techniques, chord identity, detailed tone-component approval, package readiness, PSARC registration, or installation. It never writes to the live Rocksmith installation or NoCableLauncher.

No commercial audio/DLC, private CFSM exports, Ubisoft-derived content, or generated private project data is committed by this feature.

Confirmed tone-region authority is deliberately not reinterpreted by the desktop adapter. Tone declaration/change emission belongs in the deterministic XML engine and must preserve the separate human-approved tone-component contract before that follow-on integration is considered complete.
