# Evidence-admitted next-62 slice selection — PR #806

Tracking: [#796](https://github.com/jweter/rocksmith-cdlc-generator/issues/796), particularly slices 56 and 62.

## Failure mode

The previous Execution Director could return `EXECUTE_NEXT_SLICE` merely
because no open PR or P0/P1 issue was detected. It did **not** select an
actual canonical engineering slice or prove that prerequisite work was merged,
the required Windows CI succeeded, or external authorization was available.
An hourly worker could repeatedly select model/network work which could not
possibly meet its prerequisites.

## Contract and verification

The existing public GitHub issue #796 is the **only** title, acceptance and
checkbox status source. The new `engineering/rocksmith-slice-dependencies.json`
contains only explicit prerequisite IDs, mandatory independent external
evidence codes, and verified-merge lookup receipts; it does not copy all
62 titles or change their priority order.

The `slice_readiness` module parses issue #796 using its strict 62-ID parser
and validates the dependency graph. It refuses missing rules, duplication,
invalid IDs, cyclic prerequisites, malformed evidence keys and malformed
receipts. A checked box is **not** independent proof.

**Semantic-drift protection:** the entire reviewed 62-item queue is
fingerprinted with a Git blob content hash over each immutable ID,
group, title and acceptance criterion. Checkbox `[ ]`→`[x]` progress
does not change this fingerprint. But any other revision to a work item's
meaning invalidates the queue graph until the prerequisite model is
re-reviewed. Every completed-item receipt additionally stores the SHA-256
of its own reviewed ID/title/acceptance, so an older successful PR cannot
be reused to prove a newly rewritten prerequisite. These checks happen
**before** eligible work is selected and before remote PR receipts can
unlock dependencies.

For every checked item with a documented receipt, the director asks the
authenticated read-only GitHub API to confirm: the PR is **actually merged**
and closed; its original head and resulting merge commit match the receipt;
all exact-head GitHub Actions jobs `Python 3.12 tests`,
`Windows 3.12 + PSARC bridge` and `Windows desktop app` are successful;
and there are no missing check-run pages. A missing, stale, mismatched,
failed or unreachable response leaves the corresponding item unverified
and cannot unlock dependent work.

When existing-PR, P0/P1 or remediation priorities apply, this new logic
does not interfere: those policies still win. When generic new-slice
admission is possible, the director examines **all 62** canonical IDs and
selects the earliest unchecked `READY_FOR_ENGINEERING` task whose declared
dependencies are independently verified and whose external requirements
are satisfied. Otherwise it returns a **HOLD** decision. The execution
plan includes both blocked prerequisites and ready candidates, so the
worker can move to a parallel-safe task rather than repeatedly announcing
the same missing model or Windows sandbox.

## External authorization boundary

For now, no owner/network/model/GPU/private-gameplay attestations are passed
automatically to `slice_readiness`. A requirement such as
`OWNER_APPROVED_OFFLINE_MODEL_PILOT`,
`WINDOWS_HOME_NETWORK_SANDBOX_AUTHORIZED`, or
`AVAILABLE_RAM_7_GIB` remains **BLOCKED**, even if the task's other
dependencies merged. A future integration must independently authenticate
each such private/owner attestation, verify its resource and expiry state,
and respect the exact Windows owner-control switch before passing the flag.

All current decisions are **advisory**: this change launches no model,
runs no command, downloads no assets, edits no media, changes no GitHub
issue or PR, and provides **no release or merge authorization**.
`auto_execution_authorized=false`, `model_execution_authorized=false`,
`musical_pass_proven=false` are hard outputs. The existing scheduler's
freshness, no duplicate work and exact-head gates remain mandatory.

## Limitations and operational maintenance

The receipt file is a reviewable list of independently checkable merged
development dependencies. A newly completed checklist item needs an
evidence receipt (PR number, exact head and resulting merge SHA) to
unlock other work; adding a checkbox alone will never suffice. The director
checks these receipts against GitHub on every eligible plan, rather than
trusting a local cached PASS. This introduces a bounded amount of
additional read-only API traffic.

`READY_FOR_ENGINEERING` means only that the prerequisites for starting
a **bounded engineering slice** are met; it cannot assert a completed
feature, model correctness, actual Rocksmith/PSARC gameplay, current
private Product Reality, owner permission, or that the task's future PR
will pass tests.

The acceptance for #796 slice 56 is that the actual Execution Director
rather than an inert sidecar enforces this prerequisite decision, and
negative tests demonstrate no false admit from bad issue status, stale
PR/CI, missing graph edges, or absent private approvals. Slice 62 remains
pending until the real worker demonstrably consumes the selected next
slice and begins a new bounded PR autonomously.

## Verified receipt maintenance after PRs #806–#808 (2026-11-21)

The canonical 62-slice queue progressed to **19 checked** tasks after three
independently reviewed merges; the original dependency contract still had
only 16 receipts. This is intentionally fail-closed, but would unnecessarily
block slice 21 behind the merged slice 10 until corrected.

The original PR heads, actual final merge SHAs, and successful exact-head
Python/Windows PSARC/Windows Desktop checks were independently verified:

| Slice | PR | Exact PR head | Actual merge SHA |
| --- | --- | --- | --- |
| 10 | #807 | `826274daa9348921ef190e45833b9746bb81e9eb` | `0d3be0f716847f34f7f83b662a90c08f906df260` |
| 20 | #808 | `67730eb63c41fe1f330c693fb3c35b4bde548b06` | `abfb5a9f2b147133a8f93dad85ec4e3756eefed5` |
| 56 | #806 | `184f8b35f38618b1d7b91ac618a310016afe5ae0` | `ac478dce644cbd85db4a8083b97691253e56c2b7` |

Receipts pin the exact **SHA-256 of the public issue's reviewed title and
acceptance**, never only the checkbox or PR ID. The complete 62-item semantic
queue revision fingerprint stays unchanged because checkbox progress does not
change task meaning. Tests deliberately break one PR's head, merge, pending CI
or missing Windows check independently, and verify that its own dependent
slice is blocked without borrowing another PR's CI.

The earliest newly eligible **engineering candidate** is slice 21, a safe
host concurrency control—not authorization to execute an audio model. Missing
Windows Home offline isolation, licensed model inference, independent Bass
truth, two-bar timing repair and Rocksmith gameplay PASS remain unproven.
A receipt maintenance PR closes no additional canonical task checkbox.

## Slice 21 post-merge evidence (2026-11-21)

After independent exact-head review and green CI, #810 was merged as
`2fd6bd3c1451d28bbadf61d2231f84457dde5ad1` from original PR head
`80805fcb6f414c2d796b0be04f877c169adcb9ec`.
The public #796 acceptance statement, “Model run deferred while unrelated
workloads reduce RAM”, is bound by its own SHA-256 receipt. Receipt count is
now **20** for 20 checked items. The next earliest unblocked engineering
candidate is **#796 slice 28**, the unrelated/percussion-only Bass
false-positive negative test, not an external model inference request.
A new receipt still does not grant model execution, network isolation,
song timing or gameplay correctness. Missing/newer pending exact-head CI
for #810 leaves its checkbox checked but its proof unverified.
