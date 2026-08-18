## Purpose

Describe the single coherent change and the roadmap/issue evidence that authorizes it.

## Verification

- [ ] Targeted tests/checks were run locally when practical.
- [ ] New or changed behavior has deterministic regression coverage where appropriate.
- [ ] `python scripts/check_automation_readiness.py` passes.
- [ ] Documentation matches the implemented behavior.
- [ ] `docs/project-status.yaml` was updated if milestone truth, continuation, blockers, or other durable project state changed.
- [ ] No commercial/private source material or restricted derived assets were committed.

## Autonomous merge gate

A scheduled agent must **not** merge this PR until fresh CI for the current head SHA shows both repository-required workflows successful:

- `CI`
- `Windows Desktop`

The PR must also be mergeable with no unresolved blocking review, correctness, safety, licensing, provenance, or product-policy concern.

Advisory bot comments or unavailable optional code-review services are not failures unless repository policy explicitly promotes them to a required check/review.
