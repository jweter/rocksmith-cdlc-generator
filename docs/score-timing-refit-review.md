# Bounded score-timing refit review

Sparse human score anchors can now produce a deterministic bounded refit preview between neighboring reviewed correspondences. A separate acceptance contract records the exact shared-timing candidate and exact bounded-refit preview that a human reviewed.

Acceptance is persisted at `review/score_timing_refit_acceptance.json`. The evidence contains the full reviewed candidate plus the full refit preview, including the recording, score, authority-track, and authority-output provenance already carried by those models. Loading current acceptance rebuilds the candidate and preview and rejects the evidence if either object has changed.

The acceptance write path revalidates the current candidate and preview while holding the score-mapping transaction lock. If the candidate or preview changed after it was shown to the user, acceptance fails closed and the user must refresh and review again. This mirrors the existing exact-candidate promotion boundary and prevents a human from approving one timing proposal while a different proposal is persisted.

This acceptance is still review evidence only. It does not write or replace `analysis/shared_timeline.json`, does not satisfy shared-timing promotion, and does not change Bass, Lead, or Rhythm timing. A following Song Workspace slice can render the bounded preview and invoke this contract only after explicit human approval; a later authority slice can define how accepted bounded regions become a promotable shared timeline without extrapolating outside reviewed anchors.

All existing source-rights, score-mapping, source-acceptance, tone, packaging, live Rocksmith, and NoCableLauncher boundaries remain unchanged. No commercial audio, tab content, or Ubisoft-derived material belongs in repository fixtures.
