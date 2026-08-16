# Guided song readiness

The primary desktop product translates the internal workflow plan into a user-facing **Song progress** surface. The normal authoring path should answer four questions immediately:

1. How far through the current song is the deterministic authoring workflow?
2. Does the application need a human decision now, or can it continue automatically?
3. What is the next meaningful action in plain language?
4. Can the application take the user directly to the control that resolves that action?

## Product behavior

Both the packaged Windows application and the `cdlc-desktop` entry point launch `GuidedDesktopApp`, a thin composition layer over the existing `ProductDesktopApp`.

The guided layer shows:

- a prepared/progress percentage based only on required workflow steps;
- a prominent `Needs you` state only when the **currently actionable** workflow step requires human judgment;
- a plain-language next action such as confirming Bass/Lead/Rhythm score tracks or reviewing shared song timing;
- `Continue Automatically` when the earliest unresolved required step is deterministic work that can run safely;
- a context-sensitive next-step button that routes to the existing authoritative control rather than asking the user to hunt through menus.

Current direct routes are deliberately narrow and reuse existing review surfaces:

- source-rights review → **Rights / Provenance** tab, with the first current source that still requires explicit rights review selected automatically;
- Bass/Lead/Rhythm score mapping → **Score & Mappings** tab;
- score alignment/shared-timeline/final generated-draft review → **Song Workspace**;
- deterministic work → **Continue Automatically**;
- any human gate without a known safe direct editor → **Workflow** details instead of guessing which control should grant authority.

The guided Rights / Provenance choices are built from the same `ProjectSourceInventory` that creates the source-rights gate. That means manifest recording audio and intake-backed sources such as MIDI, Guitar Pro, MusicXML, PSARC, or queued-adapter receipts remain selectable when they are current project sources. The desktop preserves each inventory item's `human_rights_review_required` and `rights_class` state rather than reducing the item to only a hash. Sources already resolved by explicit intake classification therefore stay visibly reviewed and are skipped when the guided action targets the next unresolved source.

Selecting the unresolved rights source is navigation only. It prevents an already reviewed or explicitly classified source from remaining selected when another current source still blocks progress; it never records or infers a rights decision.

Later blocked human steps are dependencies, not premature requests to the user. For example, a future review queue must not produce `Needs you` while audio normalization is the actual next runnable action.

Optional workflow helpers do not reduce the progress percentage. The planner's terminal `human-review` step is intentionally different: once validation has produced that review queue it remains an explicit human action, but it counts as prepared progress because there is no persistable `complete` state for that planner step. A project can therefore show **100% prepared** while still truthfully saying **Needs you: review the generated song draft**.

The percentage is deliberately labeled **prepared**, not **ready**. It describes deterministic workflow preparation and must never be interpreted as musical approval, validation approval, package readiness, or installability.

Advanced workflow details, provenance state, logs, XML export, DLC Builder handoff, and other diagnostic/power-user surfaces remain available underneath the guided product layer.

## Authority boundary

Song progress and guided routing are presentation/navigation only. They do not approve or infer:

- rights/provenance;
- score-track mappings;
- timing acceptance;
- notes, positions, fingering, techniques, chords, or tones;
- validation or package readiness;
- PSARC integrity or installation safety.

The routing layer never invokes a human confirmation automatically. It only opens the existing control where that decision can be reviewed and explicitly made. Unknown human gates fail safe to workflow details rather than being mapped speculatively to an editor.

The progress model derives its state from the existing authoritative `ProjectWorkflowPlan` and therefore cannot turn confidence, progress, navigation, or a percentage into authority.

## Product direction

This is the convergence path toward the intended normal workflow:

`recording + complete score → automatic setup → only necessary human review → build Rocksmith song`

The next usability work should continue collapsing required human review into direct, contextual actions inside the Song Workspace. Once those guided review actions are coherent, the product can add one validation-gated **Build Rocksmith Song** path while keeping the current advanced tools available for diagnosis and power users.
