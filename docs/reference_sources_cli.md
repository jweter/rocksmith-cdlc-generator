# Reference-only source workflow

`cdlc-reference` records public streaming/video pages as discovery and version-identification evidence without obtaining media bytes.

Examples:

```text
cdlc-reference add projects/artist-song "https://www.youtube.com/watch?v=..." --name "Official studio upload" --provider YouTube --version "2011 remaster"
cdlc-reference list projects/artist-song
```

Reference records are metadata only. They retain the public URL, display name, provider, optional version hint, optional review notes, and the enforced `streaming_reference_only` intake descriptor. The registry rejects descriptors that claim local bytes or a locally ingestible source.

This command intentionally does **not** download, rip, transcode, probe, or cache audio/video from YouTube or other streaming services. If usable audio is needed, it must enter through the separate local/licensed source workflow (`cdlc add-source`) with its own provenance classification.

Reference records are project-local under `sources/references/`, which remains beneath the gitignored `projects/` workspace. Human review remains responsible for deciding whether a reference actually identifies the correct studio/live/remaster version.
