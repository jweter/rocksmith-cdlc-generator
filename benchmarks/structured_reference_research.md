# Structured-reference research records

Issue #45 tracks structured-reference research for the 20-song benchmark candidate bank.

`BenchmarkSourceResearchRecord` is the metadata-only record for this research step. When a structured source is found, it requires an HTTP(S) source-page URL and a human-readable title. Local filesystem locations and source bytes remain outside the model.

`benchmarks/structured_reference_research.yaml` is the canonical manifest. It stores BMARK-001 and BMARK-002 directly and declares the committed BMARK-003 and BMARK-004-through-BMARK-020 YAML sidecars in `record_files`.

Consumers should call `load_benchmark_source_research_manifest(...)` with the canonical manifest path. The loader resolves the declared sidecars, validates every record, rejects duplicate benchmark IDs, and only permits repository-relative YAML sidecar references.

The canonical manifest now resolves all 20 candidates. Research metadata remains separate from benchmark provenance and human acceptance; discovery alone does not promote a candidate to trusted ground truth.
