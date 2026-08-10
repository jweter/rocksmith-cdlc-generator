# ADR-027: Auditable PSARC registration

## Context

The project can now validate Bass/Lead/Rhythm arrangements, export Rocksmith XML, create one multi-arrangement DLC Builder project, and stage/hash every build input. The remaining real-toolchain boundary is manual: a human opens DLC Builder, creates a PC `.psarc`, and then registers that package back into the project.

Previously `register-psarc` verified only the PSARC magic/compression bytes and copied the file into staging. It did not prove that the DLC Builder project and input assets were still identical to the files that had passed the staging gate. A user could stage, edit an XML or audio file, build, and still receive a superficially valid receipt.

The pinned `Rocksmith2014.NET` PSARC implementation defines a 32-byte header with:

- magic `PSAR`;
- version 1.4;
- compression method `zlib`;
- ToC length;
- ToC entry size/count;
- block allocation size;
- archive flags.

## Decision

Upgrade build readiness and PSARC receipts to schema version 2.

`stage-build` now records:

- SHA-256 of the selected `.rs2dlc` file;
- SHA-256, size, path, and semantic role for every referenced audio/art/XML asset;
- the configured-arrangement validation status.

`register-psarc` now requires an existing build-readiness manifest. Before accepting a package it:

1. reruns the configured-arrangement validation gate;
2. verifies the staged `.rs2dlc` still exists and matches its recorded SHA-256;
3. re-resolves all DLC Builder inputs and compares role/path/size/SHA-256 to the staging manifest;
4. rejects registration if any staged input changed;
5. parses the full 32-byte PSARC header and requires `PSAR`, version 1.4, and `zlib`;
6. copies the PSARC into project staging and verifies the copied file hash matches the source;
7. writes a receipt containing the PSARC header metadata, package SHA-256, build-readiness SHA-256, `.rs2dlc` SHA-256, and the complete input-asset snapshot.

## Trust boundary

This does **not** cryptographically prove that DLC Builder generated the PSARC from those staged inputs; DLC Builder remains an external manual tool. It does establish a reproducible evidence chain around the exact files the generator approved and refuses to register a package after those files drift.

The generator still never writes the package into the live Rocksmith installation. Installation remains a deliberate human action after receipt inspection.

## Consequences

- `register-psarc` now requires `stage-build` or `launch-dlcbuilder` to have run first.
- Any change to the `.rs2dlc`, arrangement XML, song audio, preview audio, or artwork invalidates the staging snapshot and forces restaging.
- PSARC receipts contain enough header and provenance data to diagnose the first real DLC Builder/Rocksmith package test.
- Future deeper PSARC inspection can extend the receipt without weakening this input-integrity boundary.
