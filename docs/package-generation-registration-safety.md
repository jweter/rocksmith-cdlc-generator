# Package-generation safety for PSARC registration

This contract prevents package registration from publishing stale installation readiness while arrangement/package state is being rebuilt.

## Problem

A PSARC registration can take long enough to overlap a Bass/Lead/Rhythm rebuild. Without an independent generation identity, registration could load an old `build_readiness.json`, a rebuild could invalidate package state, and registration could then recreate `psarc_receipt.json` for the old package with `safe_for_manual_installation=true`.

## Generation contract

- `build/package_generation.json` is project-local package-generation authority.
- A fresh staging pass publishes a new generation and removes any prior staging/receipt state.
- Bass remapping and shared Lead/Rhythm rebuilds advance package generation **before** invalidating package derivatives.
- `build/staging/build_readiness.json` records the generation it was created for.
- `build/staging/psarc_receipt.json` records the same generation.
- PSARC registration validates the exact generation and readiness SHA before receipt publication and again after atomic receipt replacement.
- If generation/readiness changes during registration, the attempted receipt and staged PSARC are removed and registration fails closed.
- If invalidation wins after the final registration check, the invalidation path removes the staging directory itself.

This is generation-based serialization, not a claim of an operating-system-wide transactional filesystem lock. The safety property is that an old registration cannot remain published as current/safe after a newer chart/package generation wins.

## Authority boundaries

The generation marker carries no musical or package approval authority by itself. It does not accept source rights, score mappings, timing, pitch, fingering, techniques, tones, validation, or installation readiness. `safe_for_manual_installation` still requires the existing deep package inspection gate.

The generator never copies a PSARC into the live Rocksmith installation and never modifies NoCableLauncher.

## Recurring-defect prevention

This implements the recurring-defect rule tracked in #193: downstream derivatives must either bind to current upstream provenance/generation or be conservatively invalidated before replacement authority is published. Related correctness issue: #165. Root-cause cross-link: #194.
