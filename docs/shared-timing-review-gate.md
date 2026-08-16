# Shared timing review gate

The Product Reality run with a full-length multi-track score exposed a confusing boundary in Song Workspace: the Timeline tab displayed one `Promote reviewed timing` control even though two different human decisions existed.

1. **Detector-beat edits** are optional corrections to the audio tempo map. Locking, nudging, exact timestamps, and refitting between locked anchors belong to this layer. These controls are not a checklist and a user is not expected to lock every detected or low-confidence beat.
2. **Shared song timing promotion** is the project-level acceptance of the current human-reviewed Bass score-to-recording alignment. This is the gate that allows Bass, Lead, and Rhythm to inherit one timing authority and continue through the multi-arrangement workflow.

The desktop UI must keep these decisions visibly separate. `Confirm beat edits` confirms only the optional reviewed detector-beat layer. `Promote shared song timing` invokes the authoritative shared-timeline promotion and refreshes project workflow state immediately afterward.

When the Bass alignment exists but no shared timeline has been promoted, Song Workspace tells the user to audition representative sections across the song and explicitly states that individual beat locks are not required. When the shared timeline is current, duplicate promotion is disabled and the UI directs the user to `Run Safe Automatic Steps`.

The shared-timeline authority remains fail-closed: promotion still validates the current recording, registered score, confirmed Bass mapping, score fan-out output, and Bass alignment provenance before writing `analysis/shared_timeline.json`. The UI guidance does not bypass or weaken any of those checks.
