# Song Workspace export readiness

Song Workspace must not infer package/export readiness from the existence of old Rocksmith XML files alone.

For a configured arrangement to report `export_xml_ready`, all of the following must be true:

- the arrangement draft is current for the active project authority;
- a readable validation report exists;
- validation allows packaging (`can_package=true`);
- the expected Rocksmith XML export exists.

Overall workspace health may report `READY` only when every configured arrangement satisfies that export-readiness contract **and** the current multi-arrangement workflow plan has no required unfinished work. `optional` planner steps are terminal and do not block readiness. The legacy `human-review` step can remain `ready` after validation because it has no separate persisted completion authority; current package-eligible validation plus current exports are the concrete evidence used at this boundary. Any blocked step or ready automatic step still prevents `READY`.

Bass mapping has an additional conservative invalidation boundary because `bass_mapped.json`, Bass validation, and Bass XML do not yet share one provenance manifest comparable to the shared Lead/Rhythm draft contract. Re-running Bass mapping removes the prior Bass validation/export artifacts and both DLC Builder and returned/staged package state before publishing the replacement mapping. A cleanup failure aborts the remap rather than leaving new Bass authority beside stale installable output.

These rules prevent old chart/validation/XML/package artifacts left on disk after mapping or upstream-authority changes from presenting the project as ready before deterministic regeneration/revalidation runs.

The readiness rule itself is read-only product state. Bass remap invalidation only removes downstream derivative/package staging that is no longer current. Neither behavior accepts score mappings, source rights, timing, fingering, techniques, tones, validation decisions, or package readiness on the user's behalf, and neither modifies imported score/fan-out data, the live Rocksmith installation, or NoCableLauncher.
