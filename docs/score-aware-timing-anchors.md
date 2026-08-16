# Score-aware timing anchors

Product Reality testing showed that asking a human to review hundreds of anonymous detector beats is the wrong interaction model. Timing review should instead use a sparse set of meaningful correspondences between the registered structured score and the recording.

The first score-aware anchor slice introduces provenance-bound review evidence at `review/score_timing_anchors.json`. Each anchor records a symbolic source beat index, its reviewed recording time, and whether the human confirmed the current proposed alignment or manually marked that score beat at the recording cursor.

Anchor evidence is bound to the current recording hash, registered score hash, confirmed Bass authority track, and authority-output hash. If any of those inputs change, the evidence is stale and must not be reused silently. Score anchors must remain monotonic in both symbolic beat order and recording time so they can later support a deterministic bounded refit. Every upsert is revalidated before persistence, so moving or reconfirming an anchor across a neighboring correspondence fails without corrupting the review file.

Manual anchors must remain inside the current recording duration. Their `candidate_time_seconds` comparison value is the current score-to-recording transform evaluated for that exact symbolic score beat, including interpolation between stride-spaced automatic alignment anchors; it is never borrowed from a merely nearby score beat.

The persisted anchor-review schema is version 2. Schema-version-1 evidence predates the duration and exact-candidate-time integrity rules and is intentionally not reused or migrated. When a project carries version-1 evidence, loading the review contract discards those legacy anchors in memory and presents a fresh empty version-2 review so the user can immediately re-review them through normal product actions. Unknown future schema versions and malformed current evidence still fail closed rather than being silently discarded.

Song Workspace now exposes this evidence directly while an unpromoted validated shared-timing candidate is available. `Confirm proposed score anchor` records the proposed score beat nearest the recording cursor after an explicit confirmation dialog. `Mark score beat here…` lets the user identify which symbolic score beat occurs at the current recording cursor. Automatic candidate anchors remain hollow diamonds on the Timeline; human-reviewed score anchors are drawn separately as filled markers. The UI reports how many anchors were confirmed from the proposal versus manually marked.

This remains evidence-only. Score-aware anchors do not yet alter the shared timeline, satisfy the shared-timing promotion gate, or automatically refit timing. The promotion dialog explicitly states that sparse human anchors do not modify the candidate in this version. Regional refitting between neighboring human anchors remains a follow-up slice. Human timing acceptance remains required.

The current imported score contract exposes a symbolic beat index but not reliable measure/section identity for every supported source format. The UI therefore displays `score beat N` rather than inventing a bar number. Bar/beat/section labels can be layered on when the importer exposes that identity authoritatively.
