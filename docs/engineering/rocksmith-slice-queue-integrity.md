# 62-slice queue integrity and machine-verified status scope

Tracking issue: [#796](https://github.com/jweter/rocksmith-cdlc-generator/issues/796).

## Purpose

A long multi-PR engineering queue can silently drift: a slice may be
duplicated, omitted, renumbered, moved into the wrong milestone group, or
given a blank acceptance criterion. Those mistakes make autonomous slice
selection unsafe even when a previous merge succeeded.

The public issue body remains the canonical queue. This change **does not
create a second static copy of all 62 tasks**. Instead,
`slice_queue_integrity.py` parses that issue body's 62 checkbox lines and
requires:

- Every two-digit ID from 01 through 62 appears **exactly once** and in order.
- Each checkbox has a meaningful title and nonempty testable acceptance
  statement in the original `**ID. Title** — Acceptance.` format.
- Tasks stay in ordered A–F groups with the approved quotas
  A:12, B:10, C:12, D:10, E:10, F:8.
- A missing, duplicated, malformed or ambiguously edited entry fails closed.

The `Rocksmith Slice Queue Integrity` GitHub workflow fetches the
**current live issue #796** with a read-only repository token and runs this
validator on pull requests, explicit dispatch and issue-body edits.
No action is taken on issue #796 itself; it is read-only.

For local review of a saved copy of the issue body:

```powershell
cdlc-slice-queue-validate --issue-markdown C:\RocksmithLocal\next-62-issue.md
```

The command emits a local JSON count and list of completed/pending item IDs
with `QUEUE_STRUCTURALLY_VALID_NOT_PROOF_OF_MERGE`. No model, task,
subprocess, phone home or source audio is accessed by the Python parser.
The GitHub workflow itself reads only the public issue body.

## Critical proof distinction

A checked Markdown box is **not independent evidence that its code merged**,
that CI passed, or that actual Rocksmith gameplay is correct. This
validation establishes *queue structure only*. Exact-head PR checks,
review resolution, private Product Reality and licensed model/gameplay
requirements are still mandatory separately. The reporter explicitly says
`external_evidence_required=true`,
`auto_execution_authorized=false`, and
`musical_pass_proven=false`.

This completes #796 slice 55 only when the live GitHub issue #796 has been
validated by the new workflow and all exact-head checks are green.
It does not complete automated slice selection (#62) or prove that
blocked tasks can be safely executed.
