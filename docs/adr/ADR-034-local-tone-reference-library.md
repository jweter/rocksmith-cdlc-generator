# ADR-034 — Local Rocksmith Tone Reference Library

## Status
Accepted

## Context
The generator can now research a real-world rig, map evidence to abstract Rocksmith tone families, bind those families to real locally available Rocksmith devices, and require explicit human approval. Choosing useful starting knob values remains difficult if the generator treats each device independently.

A user's installed Rocksmith library contains a large private corpus of actual Rocksmith tone configurations. Official arrangements are especially valuable because their amp, cabinet, effect placement, knob values, descriptors, and tone-change behavior were authored specifically for Rocksmith. Community CDLC can also be useful but must not carry the same authority by default.

The application must not upload, redistribute, or commit proprietary game packages or extracted Ubisoft manifests.

## Decision
Build a private, local, derived tone-reference library from `.psarc` files already present on the user's machine.

The library stores only normalized technical reference records needed by the generator:

- source package path and SHA-256 provenance;
- source classification (`official_rocksmith`, `custom_dlc`, `user_created`, `unknown`);
- artist/title/album metadata when available;
- Lead/Rhythm/Bass arrangement role;
- tone key/name/descriptors and volume;
- Rocksmith tone component slots, device keys/names/types/categories, and knob values;
- tone-change timestamps and target tone keys;
- deterministic tone fingerprints for duplicate/equivalent-chain analysis.

The repository contains code and schemas only. The user's generated library remains private/local and must not be committed.

## Authority weighting
Reference ranking starts with these conservative weights:

1. official Rocksmith tone: `1.00`
2. user-created/explicitly reviewed tone: `0.75`
3. community custom DLC tone: `0.65`
4. unknown package origin: `0.45`

These weights are priors, not assertions of musical correctness. Later audio similarity, external rig evidence, and explicit human review can contribute additional signals.

## Incremental indexing
A full installed DLC collection may contain hundreds or thousands of packages, so rescanning must be incremental.

For planning, the index records file path, size, and nanosecond modification time. Only new or changed files are sent to the expensive extraction step. During extraction the complete package SHA-256 is calculated and stored as immutable provenance.

Deleted packages are removed from the active derived index. No scan operation modifies the Rocksmith installation.

## Similarity
The first reference search is deterministic and transparent:

- arrangement roles must match;
- requested device-key overlap contributes most of the similarity score;
- descriptor overlap contributes secondary evidence;
- source authority weights the final score.

Later versions may add normalized knob distance, signal-chain topology, audio embeddings/features, researched real-world rig similarity, and section/use labels such as clean verse or lead solo.

## Privacy and rights boundary
- Scan only local files the user directs the application to inspect.
- Never download official DLC to populate this library.
- Never upload PSARC files or extracted proprietary manifests.
- Never commit generated tone-reference data to the repository.
- Treat the library as a private derived index used to select starting points for human review.

## Consequences
This turns tone generation from blind knob synthesis into retrieval from empirically used Rocksmith configurations. Users with large legitimate DLC libraries gain a richer private reference corpus automatically.

The next implementation step is to extend the existing local Rocksmith2014.NET/PSARC bridge with a read-only tone-extraction command that emits the normalized records defined here.