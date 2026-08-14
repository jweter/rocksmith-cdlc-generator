# Reference-only source workflow

`cdlc-reference` records public streaming/video pages as discovery and version-identification evidence without obtaining media bytes.

Examples:

```text
cdlc-reference add projects/artist-song "https://www.youtube.com/watch?v=..." --name "Official studio upload" --provider YouTube --version "2011 remaster"
cdlc-reference list projects/artist-song
cdlc-reference select projects/artist-song "https://www.youtube.com/watch?v=..." --note "Confirmed album version"
cdlc-reference selected projects/artist-song
cdlc-reference context projects/artist-song
cdlc-reference show-context projects/artist-song
```

Reference records are metadata only. They retain the public URL, display name, provider, optional version hint, optional review notes, and the enforced `streaming_reference_only` intake descriptor. The registry rejects descriptors that claim local bytes or a locally ingestible source.

`select` is an explicit human-review action. It can only select an already registered reference URL and writes `sources/reference_selection.json`, outside the registry directory so normal reference listing remains type-safe. The selection records the chosen URL plus the registered display/provider/version metadata and an optional confirmation note. If the underlying reference record is later removed, loading the selection fails rather than silently trusting stale evidence.

`context` creates `metadata/recording_context.json`, a machine-readable downstream handoff that snapshots the current human-confirmed reference selection together with `metadata/selected.json` when a MusicBrainz candidate has also been explicitly selected. `show-context` prints that persisted artifact. A reference selection is required; catalog metadata remains optional so version review can happen before catalog matching.

When DLC Builder album/year values are omitted, metadata-derived suggestions come only from this reviewed recording-context snapshot. Editing or reselecting `metadata/selected.json` later does not silently change a build; run `cdlc-reference context PROJECT` again after reviewing the new pairing. Explicit `--album` and `--year` values remain valid without a recording context.

The recording context is provenance only. It does **not** authorize downloading or ingestion, does not make referenced media benchmark-eligible, does not automatically accept musical content, and does not imply redistribution rights. Rebuilding the context is an explicit action after changing either the selected reference or selected catalog metadata.

This command intentionally does **not** download, rip, transcode, probe, or cache audio/video from YouTube or other streaming services. If usable audio is needed, it must enter through the separate local/licensed source workflow (`cdlc add-source`) with its own provenance classification.

Reference records are project-local under `sources/references/`, the selected-reference artifact is under `sources/`, and reviewed recording context is under `metadata/`; all remain beneath the gitignored `projects/` workspace. Human review remains responsible for deciding whether a reference actually identifies the correct studio/live/remaster version.
