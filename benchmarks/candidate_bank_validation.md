# Candidate bank validation

`rocksmith_cdlc_generator.candidate_bank_validation.validate_candidate_bank()` is the deterministic validation entry point for `benchmarks/candidate_bank.yaml`.

The validator enforces schema version 1, required candidate metadata, benchmark ID format, positive finite known durations, allowed tier/reference/library statuses, unique benchmark IDs, and contiguous unique ranks beginning at 1. The repository candidate bank itself is covered by regression tests, so malformed benchmark metadata fails CI rather than silently entering the research backlog.

Candidate entries are metadata-only by contract. At any depth inside a candidate, field names containing standalone `path`, `file`, `filename`, `filepath`, or `asset` tokens, including plural forms, are rejected. This prevents location-bearing or asset-bearing fields from entering the committed candidate bank while still allowing ordinary provenance notes and review rationale.

This validator does not promote a structured reference or comparison source to trusted ground truth. Human review and explicit source acceptance remain separate gates under the benchmark provenance contract. Source material itself remains outside Git.
