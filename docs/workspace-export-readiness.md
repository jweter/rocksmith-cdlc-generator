# Song Workspace export readiness

Song Workspace must not infer package/export readiness from the existence of old Rocksmith XML files alone.

For a configured arrangement to report `export_xml_ready`, all of the following must be true:

- the arrangement draft is current for the active project authority;
- a readable validation report exists;
- validation allows packaging (`can_package=true`);
- the expected Rocksmith XML export exists.

Overall workspace health may report `READY` only when every configured arrangement satisfies that export-readiness contract **and** the current multi-arrangement workflow plan has no incomplete steps.

This prevents old chart/validation/XML artifacts left on disk after mapping or upstream-authority changes from presenting the project as ready before deterministic regeneration/revalidation runs.

The rule is read-only product state. It does not accept score mappings, source rights, timing, fingering, techniques, tones, validation decisions, or package readiness on the user's behalf, and it does not modify imported score/fan-out data, the live Rocksmith installation, or NoCableLauncher.
