# Project source inventory

`cdlc-sources PROJECT` prints a read-only JSON inventory of the material and provenance state attached to one local CDLC project.

The inventory combines:

- local source intake receipts written by `cdlc add-source`;
- recognized format and adapter status;
- rights/provenance review state;
- queued sources whose parser adapter is not implemented yet;
- registered public reference-only URLs;
- whether a human-confirmed recording/version reference has been selected;
- whether `metadata/recording_context.json` has been built.

It also emits a deterministic `next_actions` list. The command does not execute parsers, download media, change rights classifications, select references, or promote any source to benchmark/ground-truth status.

Example:

```text
cdlc-sources projects/artist-song
```

A project can therefore accept broad source material while still making unresolved parser and provenance work visible instead of silently treating every input as equally trusted or equally supported.
