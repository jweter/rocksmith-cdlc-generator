# BWV1007 local vision candidate recognizer

Status: implementation slice

This slice connects the private photographed-score pipeline to a local multimodal model without allowing the model to become musical authority.

## Implemented path

```text
registered private page
  -> hash verification
  -> normalized private derivative
  -> notation/TAB system segmentation
  -> measure segmentation
  -> one private measure crop at a time
  -> loopback-only Ollama vision request
  -> schema-constrained note/rest candidates
  -> deterministic TAB-vs-notation / timing checks
  -> review-required printed-notation fixture
```

The recognizer currently defaults to `gemma3:4b`, but the model name is configurable. Image bytes are refused for any Ollama endpoint whose hostname is not loopback (`127.0.0.1`, `localhost`, or `::1`). The generated candidate JSON and optional unreviewed fixture stay under the private project directory and are already excluded from Git by the private/derived score rules.

## Authority boundary

Vision output is candidate evidence only.

Every materialized note and rest has:

- `review_required=true`;
- `human_reviewed=false`;
- source-page / measure-region provenance;
- field-level confidence inherited from the recognition candidate.

A high model confidence does not promote an event. Human review remains required before downstream authoring can treat the event as confirmed.

## Deterministic checks

The recognition boundary currently checks for:

- events extending past the measure;
- model-reported ambiguity;
- low per-event confidence;
- string indexes outside the declared instrument;
- TAB-derived pitch disagreement with independently read standard-notation pitch;
- incomplete or over-complete measure coverage.

Explicit rests are preserved as first-class timing evidence by the printed-notation adapter so silence is distinguishable from a missed recognition result.

## Laptop command

After a private score bundle is registered in a project and a local vision model is installed in Ollama:

```powershell
cdlc-score-bundle recognize-measures <PROJECT> --page 2 --limit 8 --expected-systems 5 --model gemma3:4b --bpm 80
```

This command runs preprocessing and segmentation as needed, recognizes each selected measure locally, writes the private candidate set, and also writes an **unreviewed** printed-notation fixture at the requested practice BPM.

To recognize candidates without materializing a fixture, omit `--bpm`.

The CLI rejects `--fixture-output` paths that escape the private project directory.

## Next product slice

Build the visual review surface that shows each cropped measure beside the model's proposed notes/rests, deterministic warnings, and edit/approve controls. Approval must be transactional and provenance-bound. Once a measure is approved, it can enter the existing deterministic tempo/click/Rocksmith authoring pipeline.
