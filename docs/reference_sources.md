# Reference-only source workflow

Streaming/video pages can be useful for identifying the exact studio, live, remastered, or official-upload version of a song without becoming an audio acquisition path.

`reference_sources.py` records public reference URLs beneath `PROJECT/sources/references/` as metadata-only JSON. Each record is forced through the existing `streaming_reference_only` intake class, so it cannot claim local bytes or become ingestable audio.

Intended uses:

- retain the official YouTube/artist/label page used to identify a recording version;
- record a live/studio/remaster hint for later metadata and alignment work;
- keep discovery evidence alongside the project instead of losing it in browser history;
- allow later research tooling to inspect known references without downloading media.

Safety boundaries:

- no video/audio downloading, ripping, transcoding, probing, or stream extraction;
- local, private, special-use, and credential-bearing URLs are rejected by the shared public-reference URL validator;
- reference records do not imply permission to copy, benchmark, or redistribute the underlying recording;
- a reference URL is never substituted for the user-supplied local/licensed audio source used by project ingest.

The next layer can add provider-assisted discovery that writes these same records. Provider discovery should return metadata and public page URLs only unless a provider separately exposes an explicitly licensed download path through the existing licensed-audio provider abstraction.
