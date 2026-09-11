# Engineering Error-Resolution Ledger

This ledger stores durable engineering memory for significant or recurring failure patterns. GitHub Issues/PRs remain the active work record; this file captures reusable root-cause knowledge so future development does not repeatedly rediscover the same class of defect.

Do not add every transient lint error or one-off typo. Add an entry when a failure is significant, recurring, safety/correctness relevant, or reveals a prevention rule worth preserving.

## ERR-2026-007 — GITHUB_TOKEN-created reconciliation PRs require workflow approval

- **First observed:** 2026-09-10
- **Last observed:** 2026-09-10
- **Status:** mitigated
- **GitHub references:** PR #565; follow-up PR #573
- **User-visible symptom:** Every required pull-request workflow on an automation-created status-reconciliation PR ended `action_required` before tests started.
- **Failing check / evidence:** CI, Windows Desktop, Golden Verification, Security, Control Plane, and Execution Director all terminated `action_required` with zero instantiated jobs, so no checkout/test traceback existed.
- **Root cause:** `.github/workflows/reconcile-live-status.yml` creates and updates `automation/status-reconcile` using the repository `GITHUB_TOKEN` / `github.token`. GitHub holds pull-request workflows caused by that token-created PR for approval, producing a platform gate rather than a Rocksmith code/test failure.
- **Affected surfaces:** Automated `automation/status-reconcile` PR creation/update and its downstream PR-triggered workflows.
- **Why prior safeguards missed it:** The workflow could successfully commit, push, and open the PR, while the approval policy acts only at downstream workflow dispatch. Workflow-level red/action-required state was initially indistinguishable from CI failure without inspecting job instantiation.
- **Corrective design pattern:** Classify `action_required`/startup termination with zero jobs as `PLATFORM_GATE`; do not consume repeated code-repair cycles. Authenticate automated PR creation and subsequent branch pushes with a least-privilege trusted identity when Jeremy provisions it.
- **Fix applied:** Durable regression memory records the diagnosis and scheduler routing. The permanent credential/workflow change is intentionally deferred until Jeremy creates the repository secret `STATUS_RECONCILE_TOKEN`; no credential or permission weakening is committed.
- **Verification:** PR #565 exhibited the zero-job `action_required` signature across all required workflows. PR #573 records the failure class and prevention rule; exact-head branch Preflight was GREEN before PR creation.
- **Regression protection:** Future DoWork/CI forensics must descend workflow run -> jobs before classifying a red/action-required result. Zero-job `action_required`, `cancelled`, or `startup_failure` is a platform gate unless contrary evidence exists.
- **Provenance / invalidation / safety boundary:** This diagnosis changes orchestration metadata only. It grants no musical, timing, mapping, source, validation, export, packaging, or Product Reality authority.
- **Residual risk:** Until `STATUS_RECONCILE_TOKEN` is provisioned and the reconciliation workflow is switched for both checkout/push and `gh pr create`, future bot-created reconciliation PRs may require one-time manual workflow approval.
- **Prevention rule:** Never diagnose a workflow-level `action_required` result as a product-code failure without checking whether jobs were instantiated. For automated PR workflows that must trigger downstream CI unattended, avoid repository `GITHUB_TOKEN` as the PR-creating/updating identity when GitHub's approval policy applies.

---

## Existing ledger history

The prior authoritative ledger entries remain on `main`. This focused branch appends ERR-2026-007; when reconciling this branch, preserve all existing ERR entries from current `main` and append this entry rather than replacing history.
