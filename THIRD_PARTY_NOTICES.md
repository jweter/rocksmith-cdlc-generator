# Third-Party Notices

## Editor on Fire

Rocksmith CDLC Generator uses **Editor on Fire (EOF)** as a reference implementation for mature Guitar Pro and Rocksmith authoring behavior. Portions of this project's timing design are already adapted from EOF behavior, and issue #414 establishes a standing program for additional tested parity/adaptation where useful.

### Primary current upstream

Repository: `raynebc/editor-on-fire`  
Upstream copyright: Copyright (c) 2018, T^3 Software  
Upstream license: BSD-style 3-clause license (`license.txt` in the EOF repository)

The upstream license permits redistribution and use in source and binary forms, with or without modification, provided its copyright notice, conditions and disclaimer are retained and contributor names are not used to endorse or promote derived products without specific prior written permission.

### Historical snapshot used by the first timing parity fix

Repository: `Berneer/editor-on-fire`

PR #413's initial timing investigation inspected the Guitar Pro / Go PlayAlong timing implementation in `src/gp_import.c` and related declarations in `src/gp_import.h` from this historical snapshot. The relevant behavior was the ability to synchronize symbolic beats before audio time zero, omit the pre-zero portion and continue mapping later score content through the project beat map instead of rejecting the valid transform.

New EOF audits should normally begin with the current `raynebc/editor-on-fire` lineage so later fixes are not missed. Historical forks remain useful for provenance and comparison.

### Reuse policy

This project's Python implementation is not a bundled copy of the EOF application. Relevant deterministic authoring behavior may be studied, ported, adapted or directly reused when the file-level licensing permits it and doing so is preferable to independently reimplementing mature behavior.

For substantial direct adaptations, record the upstream repository/path and preferably the source commit/SHA in the implementation PR or source documentation. Preserve required BSD attribution and conditions.

The standing audit/reuse plan is documented in:

- `docs/eof-reference-parity-program.md`
- `docs/eof-subsystem-parity-matrix.md`
- `docs/eof-upstream-fork-inventory.md`

Before directly reusing code from any third-party subtree bundled inside EOF, review that subtree's own license separately. This notice applies to EOF project code under its root license; it does not automatically cover every vendored dependency.

## Rocksmith Custom Song Toolkit and adjacent tools

`rscustom/rocksmith-custom-song-toolkit` and relevant forks are reference sources for Rocksmith XML, SNG, package and dynamic-difficulty behavior under issue #414.

Their code is **not** covered by EOF's BSD license merely because it participates in the same authoring ecosystem. Inspect the applicable project/file licenses before any direct code reuse. Until that audit is complete, treat toolkit/DDC source as behavior/design reference material rather than an automatically reusable donor codebase.
