# Emerging-Compute Applicability Policy

## Current decision

For the Rocksmith CDLC Generator, quantum computing and other exotic compute substrates have **LOW current applicability**.

That is an engineering conclusion, not a permanent ban. The project should remain capable of testing a future method if evidence makes it relevant, but agents must not introduce quantum/photonic/neuromorphic dependencies simply because those technologies are novel.

## Why classical remains the default

The project's hard problems are presently dominated by classical domains:

- audio feature extraction and onset detection;
- tempo/beat estimation;
- time-series alignment and dynamic time warping;
- transcription/arrangement inference;
- GP/audio synchronization;
- sustain and phrase-boundary correctness;
- arrangement completeness across Bass/Rhythm/Lead;
- deterministic artifact generation and validation;
- Product Reality/playability evidence.

These have mature classical numerical, signal-processing, search, optimization, and machine-learning methods. The current bottlenecks must be measured and attacked there first.

## Gate for any non-classical proposal

A quantum, quantum-inspired, photonic, neuromorphic, or other experimental-compute candidate is `NOT_JUSTIFIED` unless **all** of these exist:

1. **Measured bottleneck** — a current classical stage is demonstrably limiting quality, runtime, cost, or search tractability.
2. **Credible mapping** — there is evidence that the actual Rocksmith problem maps to the proposed method; vague claims about “optimization” are insufficient.
3. **Verified classical baseline** — the best practical current method is versioned and measured.
4. **Same measurement contract** — both methods are evaluated against the same timing/musical-quality/correctness contract.
5. **Cheap first experiment** — analytical, quantum-inspired, or simulator evaluation can test the core hypothesis without product integration.
6. **Operational justification** — expected benefit can plausibly outweigh SDK/provider/hardware/maintenance complexity.
7. **Independent verification** — a candidate win is reproduced independently before product promotion.

## Measurement contract dimensions

Any future experiment must compare at least the dimensions relevant to the stage being challenged:

- alignment error in milliseconds/beats;
- note/onset precision and recall where appropriate;
- sustain/timing correctness;
- arrangement completeness;
- deterministic reproducibility;
- runtime/wall-clock time;
- failure rate;
- CPU/GPU/memory usage;
- financial cost;
- added maintenance/operational complexity;
- final Product Reality/playability impact where the change can affect musical experience.

A faster method that degrades playable timing is not an improvement.

## Quantum-specific rule

If a credible quantum candidate ever emerges:

**classical baseline → quantum-inspired/simulator experiment → repeated evidence → independent verification → optional hardware experiment**.

Do not go directly from idea to paid QPU execution when simulation can answer the structural question.

A local benchmark win is only a bounded benchmark result. Do not call it general quantum advantage.

## Examples of outcomes

### Correct outcome today

Proposal: “Use a quantum computer to fix the two-bar timing offset.”

State: `NOT_JUSTIFIED`.

Reason: the defect is a deterministic alignment/reference-frame problem and should be diagnosed/fixed in the classical pipeline.

### Potentially testable future outcome

Proposal: a specific arrangement-search problem becomes combinatorially expensive after classical optimization is exhausted, and a documented quantum-inspired method maps precisely to the same objective.

State: potentially `ELIGIBLE_FOR_BOUNDED_EXPERIMENT`, beginning with a simulator/quantum-inspired implementation and the exact classical baseline.

### Still insufficient

Proposal: “Quantum machine learning might improve transcription.”

State: `GATHER_EVIDENCE` or `NOT_JUSTIFIED` until the method, mapping, comparator, and measurement contract are concrete.

## Protection against novelty churn

The Opportunity Sweeper should not repeatedly propose quantum work here merely because the policy exists. This document is a **negative capability** as much as a future-readiness capability: it allows the system to confidently say “not appropriate for this project.”

If another portfolio project earns a transferable, domain-independent emerging-compute pattern, Cross-Repo Pattern Distillation may propose that engineering pattern here. It must not transfer another project's domain requirements.

## Activation trigger

Do not create code, dependencies, or provider integrations from this policy alone. The trigger is a measured bottleneck plus a credible bounded experiment that survives the portfolio Emerging Compute Evaluation gate.
