# Model cache bundle manifest — source-separation preflight (slice #13)

This is a **read-only local provenance check**, not permission to download, install, redistribute, or execute a model. Existing `audio-separator` CLI remains opt-in.

## Why file-only model pinning was incomplete

A valid SHA-256 for `bass.onnx` does not cover a separate YAML/JSON configuration, companion weight file, decoder, or supporting upstream artifact. A model can be cached while its auxiliary inputs are absent or changed. Previously, those independent files were not part of the local separation acceptance receipt.

`cdlc separate-bass` now also requires `--model-manifest` before granting model readiness, with a JSON file located immediately inside the explicit `--model-cache-dir`. Each declared file is checked for expected **byte length and SHA-256** before execution and again after, including the primary model. Missing, stale, duplicate, traversal, absolute, symlinked, unbounded or malformed entries block. No other directories are searched.

## Minimal example (synthetic placeholders; hashes must be real)

```json
{
  "schema_version": 1,
  "model_filename": "bass.onnx",
  "files": [
    {
      "path": "bass.onnx",
      "sha256": "<64 lowercase hex characters for the exact file>",
      "size_bytes": 12345
    },
    {
      "path": "config/bass.yaml",
      "sha256": "<64 lowercase hex characters for this config>",
      "size_bytes": 321
    }
  ]
}
```

This example is illustrative and intentionally contains no deployable model weights or claimed license. Record actual local bytes and model-family dependencies before using the manifest.

Read-only command:

```powershell
cdlc separate-bass C:\RocksmithLocal\synthetic-project `
  --model bass.onnx `
  --model-cache-dir C:\RocksmithLocal\models `
  --model-manifest C:\RocksmithLocal\models\manifest.json `
  --model-sha256 <64-character-actual-model-digest> `
  --confirm-model-rights
```

Do not add `--execute` until resource, licensing and independently enforced network controls are separately satisfied. A successful manifest report returns `MANIFEST_DECLARED_FILES_VERIFIED` with manifest SHA-256 and declared-file count; this is **not a source-separation PASS**. The eventual private `stems/bass.json` receipt records the same manifest digest and count, so later evidence can identify the input bundle.

## Evidence boundaries

- **Proven:** every explicitly declared local file matched its exact size/digest when checked; model file matched the pinned model hash; malformed and escaping paths were refused.
- **Not proven:** that the manifest is the exhaustive upstream dependency graph, that the model or config is safe, that a model license permits this use, that the external CLI cannot contact the network, that optional plugins aren't fetched, that RAM is contained, or that a Bass-only stem was produced.
- **No download/model runtime:** tests construct tiny fake byte files and use a mocked separator. No commercial music, copyrighted stems, credentials or actual weights are committed.
- **Outstanding #15:** upstream model dependency closure remains unverified until one selected model/provider and exact loader behavior are audited against an independently validated manifest and enforced network-denial test.

See `docs/engineering/safe-bass-separator-pilot.md`, #787 and #796.
