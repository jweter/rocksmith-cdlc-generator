# Structured-reference research records

Issue #45 tracks structured-reference research for the 20-song benchmark candidate bank.

`BenchmarkSourceResearchRecord` is the metadata-only record for this research step. When a structured source is found, it requires an HTTP(S) source-page URL and a human-readable title. Local filesystem locations and source bytes remain outside the model.

`benchmarks/structured_reference_research.yaml` is the canonical manifest. It stores BMARK-001 and BMARK-002 directly and declares the committed BMARK-003 and BMARK-004-through-BMARK-020 YAML sidecars in `record_files`.

Consumers should call `load_benchmark_source_research_manifest(...)` with the canonical manifest path. The loader resolves the declared sidecars, validates every record, rejects duplicate benchmark IDs, and only permits repository-relative YAML sidecar references.

The canonical manifest resolves all 20 candidates. Research metadata remains separate from benchmark provenance and human acceptance; discovery alone does not promote a candidate to trusted ground truth.

## Tier-1 verification state

The Tier-1 benchmark candidates have explicit structured-source research records:

- **BMARK-001 — Lamb of God — Laid to Rest:** Guitar Pro's official mySongBook catalog explicitly lists a Guitar Pro arrangement, including a Guitars, Bass & Backing Track version and a Full Score. The research record is therefore classified `official_commercial_guitar_pro`.
- **BMARK-002 — Trivium — Built to Fall:** a rhythm-aware Songsterr source is verified, but this research pass did not verify an equivalent official/commercial Guitar Pro listing. It remains `other_structured_notation`.
- **BMARK-003 — Killswitch Engage — Rose of Sharyn:** a rhythm-aware Songsterr source is verified, but this research pass did not verify an equivalent official/commercial Guitar Pro listing. It remains `other_structured_notation`.

These classifications describe public discovery evidence only. They do not prove that a source has been lawfully acquired, do not import or redistribute any tab file, and do not satisfy the separate human-review/acceptance gate required before benchmark promotion.
