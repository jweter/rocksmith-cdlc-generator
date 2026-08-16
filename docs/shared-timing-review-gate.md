# Shared timing review gate

The Product Reality run with a full-length multi-track score exposed a confusing boundary in Song Workspace: the Timeline tab displayed one `Promote reviewed timing` control even though two different human decisions existed.

1. **Detector-beat edits** are optional corrections to the audio tempo map. Locking, nudging, exact timestamps, and refitting between locked anchors belong to this layer. These controls are not a checklist and a user is not expected to lock every detected or low-confidence beat.
2. **Shared song timing promotion** is the project-level acceptance of the current human-reviewed Bass score-to-recording alignment. This is the gate that allows Bass, Lead, and Rhythm to inherit one timing authority and continue through the multi-arrangement workflow.

The desktop UI must keep these decisions visibly separate. `Confirm beat edits` confirms only the optional reviewed detector-beat layer. `Promote shared song timing` invokes the authoritative shared-timeline promotion and refreshes project workflow state immediately afterward.

Before shared timing promotion can be enabled, Song Workspace builds a **read-only validated candidate** using the same recording, registered-score, confirmed Bass mapping, fan-out, source-path, source-hash, track, and alignment provenance checks used by the actual promotion path. A stale or mismatched `analysis/alignment.json` therefore remains disabled and the UI shows the rejection reason instead of presenting an actionable-looking dead end.

The validated candidate is surfaced before human acceptance. Candidate score-to-recording anchors are drawn on the Timeline as score-anchor diamonds at their mapped recording times, the UI reports candidate anchor count and overall confidence, and the cursor detail identifies the nearest source-score beat correspondence. This makes the authority transition reviewable rather than blind.

Promotion is bound to the **exact candidate instance the user reviewed**. Song Workspace passes that candidate back into the authoritative promotion call. Under the score-mapping transaction lock, the backend rebuilds the current candidate and requires model-equivalence with the reviewed one before writing `analysis/shared_timeline.json`. If the alignment, provenance, anchors, confidence, source track, or any other candidate field changed after preview, promotion fails closed and the user must refresh and review the updated candidate.

When a valid Bass alignment candidate exists but no shared timeline has been promoted, Song Workspace tells the user to audition representative sections across the song and explicitly states that individual beat locks are not required. When the shared timeline is current, duplicate promotion is disabled and the UI directs the user to `Run Safe Automatic Steps`.

The shared-timeline authority remains fail-closed: no timing is auto-promoted, uncertain musical correspondences still require human acceptance, and source-rights, score-mapping, packaging, live Rocksmith, and NoCableLauncher boundaries remain unchanged.
