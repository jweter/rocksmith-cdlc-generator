# Third-Party Notices

## Editor on Fire

Portions of the Rocksmith CDLC Generator timing design are adapted from the behavior and algorithms of **Editor on Fire (EOF)**, specifically its Guitar Pro / Go PlayAlong import timing implementation in `src/gp_import.c` and related declarations in `src/gp_import.h`.

Upstream repository: `Berneer/editor-on-fire`  
Upstream copyright: Copyright (c) 2010, T^3 Software  
Upstream license: BSD-style 3-clause license (`license.txt` in the EOF repository)

The upstream license permits redistribution and use in source and binary forms, with or without modification, provided its copyright notice, conditions, and disclaimer are retained and contributor names are not used to endorse derived products without permission.

The Rocksmith CDLC Generator's Python implementation is not a bundled copy of the EOF application. Relevant timing semantics have been ported/adapted into the project's own provenance-aware pipeline. In particular, the alignment refinement follows EOF's behavior of allowing synchronized symbolic beats to precede audio time zero, omitting only pre-zero beat content from the in-recording beat map rather than rejecting an otherwise valid synchronization.

Before directly reusing code from any third-party subtree bundled inside EOF, that subtree's own license must be reviewed separately; this notice applies to EOF's project code under its root license, not automatically to every vendored dependency in the upstream repository.
