# Issue backlog review cadence

The GitHub Issues tab is a deliberate reliability input, not a substitute for the product roadmap and not a place where defects are allowed to stagnate indefinitely.

At Product Reality and other major milestone boundaries, review the full open issue backlog and:

1. close or consolidate obsolete and duplicate issues;
2. confirm reproduction/context where practical;
3. rank safety violations, reproducible wrong output/data loss, and normal-path blockers first;
4. rank remaining issues by normal-path user impact, frequency, evidence from Product Reality sessions, and effort/value;
5. select a bounded set of the highest-value issues for the next reliability/hardening work while continuing roadmap progress;
6. leave lower-value issues documented for later passes rather than allowing them to consume the active milestone.

A newly discovered blocker, correctness/data-loss defect, or hard safety violation may interrupt roadmap work immediately. Lower-severity cleanup normally waits for the next deliberate issue sweep.

Product Reality findings should create or update focused issues with reproduction context and measured evidence. Issue priority should be revised when real-user evidence contradicts prior assumptions.
