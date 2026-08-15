# Package generation safety guard

Package/readiness artifacts must never survive an upstream authoring change as if they still describe the current song state.

## Contract

`build/package_generation.json` is a project-local generation marker. It contains a random 256-bit token representing the current package-authority generation.

Any authoring operation that invalidates DLC Builder or staged PSARC state must publish a new generation token **before** deleting stale package artifacts. The current guarded paths include:

- Bass remapping;
- Bass score fan-out;
- Lead/Rhythm shared-timeline rebuilds;
- each new `stage-build` operation.

`build/staging/build_readiness.json` records the generation used for staging. `register-psarc` refuses to proceed if that generation no longer matches the project marker, re-checks the readiness hash and arrangement gate after package inspection, publishes the receipt through a temporary file, and checks the generation again after publication. If the generation changed, registration removes the receipt and staged PSARC copy and fails closed.

## Root cause addressed

Previously a chart rebuild could delete package state while a concurrent `register-psarc` had already loaded the old readiness manifest. Registration could then recreate staging and publish `safe_for_manual_installation=true` for a package built from stale inputs.

The generation marker turns an upstream authoring mutation into an explicit authority change that a concurrent or delayed registration can detect even when filesystem cleanup overlaps it.

## Safety boundary

This guard does not approve musical content, source rights, mappings, timing, fingering, techniques, tones, validation, or installation. It only prevents stale package/readiness state from being represented as current. The application still never writes to the live Rocksmith installation or NoCableLauncher.

Related issues: #165, #193, #194.
