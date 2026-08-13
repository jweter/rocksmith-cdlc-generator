# Candidate bank validation

`rocksmith_cdlc_generator.candidate_bank_validation.validate_candidate_bank()` is the deterministic validation entry point for `benchmarks/candidate_bank.yaml`.

The validator currently enforces schema version 1, required candidate metadata, benchmark ID format, positive known durations, allowed tier/reference/library statuses, unique benchmark IDs, and contiguous unique ranks beginning at 1. The repository candidate bank itself is covered by regression tests, so malformed benchmark metadata fails CI rather than silently entering the research backlog.

This validator does not promote a structured reference, tab, or existing CDLC to trusted ground truth. Human review and explicit source acceptance remain separate gates under the benchmark provenance contract.

A follow-up slice should add a metadata-only location/asset guard before Issue #41 is closed, so committed candidate metadata cannot accidentally gain local source-file fields.
