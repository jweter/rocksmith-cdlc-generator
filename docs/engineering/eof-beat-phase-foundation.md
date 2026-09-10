# EOF-style beat-phase timing foundation

Issue #455 identified the persistent Guitar Pro timing failure as a shared phase/translation error rather than cumulative tempo drift. The recording click/beat grid is already correct in Product Reality, so the remaining timing question is which authoritative audio beat corresponds to symbolic Guitar Pro beat zero.

This slice establishes that model explicitly:

- Guitar Pro timing is reduced to symbolic fractional beat coordinates before mapping to recording time.
- Candidate alignment phases are restricted to actual audio beat-grid indices.
- The selected phase is represented by `audio_beat_start_index`, not an arbitrary free-floating seconds correction.
- Fractional beat positions are interpolated between adjacent audio beat anchors; notes are never rounded independently to clicks.
- Repeated phrases are handled by choosing the earliest strongly supported near-best phase so a later repeated riff cannot steal timing authority from the first complete score occurrence.
- Insufficient phase evidence fails closed and remains review-required.
- One solved phase can be shared by Bass, Lead, and Rhythm.

The implementation is isolated in `eof_beat_phase_alignment.py`. This foundation does not yet replace the existing project-level Guitar Pro alignment call path. The dependency-safe next slice is to route the GP project alignment workflow through this phase authority and build the resulting shared beat-to-realtime transform before generating Bass/Lead/Rhythm.

No title-specific logic, private media, or hard-coded `-4.664 s` correction is used.
