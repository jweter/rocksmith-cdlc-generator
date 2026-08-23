# Product Reality defect: "Register / Replace Score" promises a capability that does not exist

## Observed symptom

The Score & Mappings tab's score-registration button was labeled
"Register / Replace Score", and `project_score.register_project_score`'s refusal
message for a second, different score file read: "Project already has a
different registered score; explicit replacement is required." Both wordings
imply that an explicit replacement workflow exists and the user simply needs to
find it. It does not exist anywhere in the app: not in the desktop UI, not in
any `cdlc-*` CLI command. A user who picked the wrong score file (a very
plausible normal-authoring mistake) or who needed to correct/re-export a score
therefore hit an unrecoverable dead end with no actionable next step, other
than manually deleting project files outside the app -- which this project
deliberately does not document or endorse, since doing so naively (e.g.
deleting only `sources/score/source.json`) would leave Bass/Lead/Rhythm
mappings, fan-out, shared timing, and drafts referencing the old score's
authority behind: exactly the stale-derivative-state failure mode #193 tracks.

`ProductDesktopApp` (the actual shipped `cdlc-desktop` shell, via
`GuidedDesktopApp`/`LiveDiagnosticsGuidedDesktopApp`) already recognized the
"/Replace" wording was misleading and papered over it with a runtime
widget-tree rename (`desktop_shell.py`'s `_rename_button`) that relabeled the
button to "Register Score…" -- but only for that one shipped surface, and only
the button label. The base `DesktopApp` still showed "Register / Replace
Score", and the underlying error message (reached from either shell, the
moment a user actually tries a different file) still promised the
non-existent "explicit replacement" path either way.

## Root cause

The UI/error-message wording was written aspirationally for a replacement
workflow that was never implemented, and nothing kept the wording in sync
with that fact as the rest of the project matured. `docs/project-score-registration.md`
already correctly described this as deliberately refused "until an explicit
replacement workflow exists" -- but the in-product strings a user actually
sees did not carry the same honesty, and there was no test asserting the
button text or refusal message content.

## Fix

- `desktop_app.py`: the Score & Mappings tab's registration button is now
  labeled "Register Score…" at the source (matching what the shipped guided
  shell already displayed via the runtime rename), so every shell built on
  `DesktopApp` is consistent without indirection.
- `desktop_shell.py`: removed the now-redundant `_rename_button` runtime
  rename and its call site.
- `project_score.py`: `register_project_score`'s refusal message no longer
  claims "explicit replacement is required". It now states plainly that
  replacing an already-registered score is not supported yet and that
  starting a new project with the corrected file is the one path that
  actually works today.
- `docs/project-score-registration.md`: reworded to match, and to explain why
  refusing outright (rather than silently substituting) matters.

This is presentation/error-message only: `register_project_score`'s actual
behavior (refuse a different score once one is registered) is unchanged, so
no human-review, provenance, mapping, or packaging gate is weakened. If
anything, the gate's messaging is now more honest about what it does and does
not allow.

## Regression protection

- `tests/test_desktop_score_tab_layout.py::test_register_score_button_does_not_promise_unsupported_replacement`
  exercises the real `DesktopApp._build_layout` source and asserts the
  registration button reads "Register Score…" with no "Replace" wording.
  Verified to fail against the pre-fix label ("Register / Replace Score").
- `tests/test_project_score.py::test_register_different_score_requires_explicit_replacement`
  (extended) asserts the refusal message no longer contains "explicit
  replacement is required" and does contain "start a new project". Verified
  to fail against the pre-fix message.

Full suite: `python -m pytest -q` -> 1377 passed, 0 failed (1375 baseline + 2
new/extended). Also ran `python -m compileall`, `python -m pip check`,
`cdlc --help`, `scripts/check_automation_readiness.py`, and
`scripts/quality_preflight.py` -- all clean.

## Safety / authority boundary

No mapping, validation, provenance, timing, packaging, or human-review-gate
logic changed. `register_project_score` still refuses a different score
outright; this slice only makes the button label and refusal message honest
about what recourse exists.

## Residual risk

A real replacement workflow (safely invalidating every score-bound
derivative -- mappings, fan-out, shared timing, guitar drafts, validation,
XML, staged packages -- across all three arrangements) remains unimplemented
and is a larger, separate feature slice; this fix intentionally does not
attempt it and instead makes the current, deliberate limitation honestly
communicated. That larger feature, if pursued, should apply the same
generation-token/conservative-invalidation pattern #193 already documents for
Bass remapping, Bass score fan-out, Lead/Rhythm shared-timeline rebuild,
stage-build, and register-psarc, extended to cover score registration itself.
