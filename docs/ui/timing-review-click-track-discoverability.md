# Timing-review click-track discoverability

This #305 slice continues the "highest-value workflow surfaces" step after the validation-dashboard design-token adoption in PR #341, and directly addresses a #305 Product Reality finding.

## Why

Two separate Product Reality comments on #305 (2026-08-20) reported that the existing `Variable-tempo click` toggle on the Timeline screen — auditioning an audible pulse on the current beat grid during playback — was genuinely useful for judging score-to-recording timing alignment by ear, but was easy to miss because it lived among dense timing-edit controls (loop points, nudge buttons, anchor locking) rather than near Play/Stop where a listening review naturally starts. The request was to relabel it as a clearly named review aid (for example `Click Track` / `Audition Beat Grid`), place it near Play/Stop, and add a short tooltip explaining what it does.

## What changed

- `PlaybackSongWorkspaceWindow` (`song_workspace_playback_ui.py`) gained a `_build_transport_extra(transport)` hook, called in the shared transport row right after the seek buttons and before the elapsed/duration time label. The base window's hook is a no-op; this exists purely so a subclass can add a control that reads as directly associated with Play/Stop instead of being placed in an unrelated frame.
- `TimingReviewSongWorkspaceWindow` (`timing_review_ui.py`) now overrides that hook to place the click-track toggle there instead of in the "Timing review" control cluster it previously lived in. It is relabeled `🔔 Click Track` (`CLICK_TRACK_LABEL`) and paired with a short explanatory tooltip (`CLICK_TRACK_TOOLTIP`): "Plays an audible pulse on the current beat grid during playback, so you can judge score-to-recording timing alignment by ear." The authority-neutral wording is intentional because the transport can audition either human-reviewed timing or the current detector-derived beat grid when no current review is available.
- `ui_tooltip.py` adds one small, reusable `Tooltip` helper: a delayed (500 ms) borderless popup shown on hover and dismissed on mouse-leave, click, or widget destruction. It carries explanatory text only. Unlike `design_tokens.py`, this module requires `tkinter` (any caller attaching a tooltip already imports `tkinter`/`ttk` to build the widget being annotated), so it deliberately does not try to preserve the tkinter-free import contract `design_tokens.py` documents for itself.
- The toggle's underlying behavior, variable, and command (`click_var` / `_set_click`) are unchanged — only its label, tooltip, and screen position moved.

## Authority boundary

This is presentation/discoverability only. It does not change playback behavior, beat-grid computation, reviewed timing, anchors, or any validation/provenance/review authority. The click track remains exactly what it was: an optional audible listening aid, not acceptance evidence. Its tooltip deliberately refers to the `current beat grid`, because that grid may be detector-derived when a current human timing review is absent.

## Tests

- `tests/test_ui_tooltip.py` exercises `Tooltip` end to end using a fake widget/`Toplevel`/`Label` so behavior (bind wiring, hover-delay scheduling/cancellation, popup positioning, idempotent show, hide-on-destroy-context) is regression-tested without a display server.
- `tests/test_timing_review_transport_click_track.py` verifies the base hook is a safe no-op, that `TimingReviewSongWorkspaceWindow._build_transport_extra` wires the relabeled control (with the shared `Tooltip` helper) into the transport row while still calling the base hook first, and that the label/tooltip text alone (not color) carry the control's meaning. It also locks the authority-neutral wording so the tooltip cannot imply that detector-derived fallback beats are already reviewed.

## What was not done

This slice does not implement the separate #305 "NEXT REQUIRED ACTION" prominent-affordance request (a larger, cross-cutting change to how the required next workflow action is highlighted) — that remains a distinct, not-yet-started #305 slice.
