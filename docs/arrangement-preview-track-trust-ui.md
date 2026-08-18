# Arrangement Preview track source-trust controls

Issue #268 came from a Product Reality run where a real multi-track Guitar Pro score produced a four-digit flat review queue. The project now has provenance-bound whole-track source-trust acceptance, stale/current status inspection, and a UI-ready controller. This slice wires that controller into the actual Song Workspace Arrangement Preview.

The final Song Workspace displays source-track trust for the arrangement selected by the existing Bass/Lead/Rhythm role selector. It shows the current track identity, note count, acceptance state, blockers, and the exact controller-provided action label. Disabled controller actions remain disabled in the desktop UI. Status-loading errors also fail closed rather than exposing an acceptance button.

Selecting **Accept Track Source** or **Reaccept Current Track Source** invokes the existing provenance-bearing controller. The controller and acceptance layer revalidate the registered score, human-confirmed mapping, current fan-out manifest/content, tuning, explicit positions, and pitch consistency before recording human provenance. After success, Arrangement Preview reloads so the existing read-only trust projection can show current accepted trust immediately.

## Authority boundary

Whole-track acceptance covers only imported note identity and explicit string/fret positions for the exact current source track. It does not accept timing, techniques or ties, chord identity or fingering, validation findings, tones, package readiness, score mapping, or source rights. Those remain independent human review gates. The UI does not mutate score/fan-out bytes or the live Rocksmith installation, does not interact with NoCableLauncher, and does not add commercial audio/tabs, PSARCs, CFSM exports, Ubisoft-derived content, or private generated project data to the repository.
