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
