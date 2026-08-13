# Benchmark source provenance and acceptance

Every benchmark reference source must have a metadata-only provenance record before it can be treated as trusted ground truth. The source file itself stays outside Git whenever it is copyrighted or otherwise non-redistributable.

The typed contract is `BenchmarkSourceProvenance` in `rocksmith_cdlc_generator.benchmark_provenance`.

## Required metadata

Each record contains:

- `benchmark_id` such as `BMARK-001`;
- a human-readable `source_label`;
- `source_kind`: `guitar_pro`, `midi`, `musicxml`, `hand_corrected`, `existing_cdlc`, or `other`;
- an `acquisition_license_note` describing where the source came from and what use/redistribution constraints apply;
- `redistribution_status`: `redistributable`, `local_only`, or `unknown`;
- SHA-256 of the exact local source bytes;
- `accepted_by_human`;
- `accepted_by` and `acceptance_date` only after explicit human acceptance;
- `known_limitations` that remain relevant when interpreting benchmark results.

The model intentionally has **no source-path field** and rejects unknown fields. A local path is operational data, not provenance that belongs in the public repository.

## Acceptance workflow

1. Acquire a lawful reference source locally.
2. Keep copyrighted/non-redistributable source bytes outside Git.
3. Compute SHA-256 for the exact source file and create the metadata record.
4. Leave `accepted_by_human` false while the chart is only a reference candidate.
5. Review the relevant excerpt against the recording and resolve known transcription/timing/technique problems deliberately.
6. Record limitations that remain after review.
7. Only after a human explicitly accepts the reference, set `accepted_by_human` true and record both the reviewer identity and acceptance date.
8. Use the accepted source hash in later benchmark-generation provenance so a benchmark result can be traced back to the exact reviewed reference.

The contract fails closed: acceptance cannot be true without a reviewer and date, and reviewer/date fields cannot be populated while acceptance remains false.

## Safety boundary

Do not commit commercial audio, commercial tablature, private MIDI/GP files, extracted Ubisoft content, Rocksmith PSARC files, or local filesystem paths merely to satisfy provenance. Metadata and hashes are sufficient for the public record when the underlying source must remain private.

An existing CDLC may be used privately as a comparison source, but it is never trusted automatically. It must pass the same explicit human acceptance gate as any other structured source.
