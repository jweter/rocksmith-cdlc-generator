# Song Workspace refresh failure state

## Product Reality finding

When the Song Workspace snapshot builder failed, the header rendered the raw
exception text and only reset its health/progress indicators. A filesystem or
parser exception could expose a private local path or score filename, while the
rest of the window continued showing stale project, arrangement, review,
source, and timeline data from the last successful refresh.

That combination was unsafe authoring presentation: the header said refresh
failed while stale derived state still looked current.

## Correction

The refresh failure now fails closed:

- the header shows a non-color-only FAIL state and only the exception class as
  bounded diagnostics;
- raw exception messages, local paths, and filenames are not rendered;
- stale song identity, progress, next-action, arrangement rows, review rows,
  source details, and timeline drawing are cleared or marked unavailable;
- the recovery text tells the user to refresh, then verify project files and
  open Diagnostics if the failure persists;
- the review panel explicitly states that existing review requirements were
  not changed.

Regression coverage starts from a populated/stale window, raises an exception
containing a private Windows path and score filename, and verifies both
sanitization and stale-state clearing.

## Packaged-window inheritance boundary

The shipped window is a deep cooperative-refresh stack. Every subclass now stops immediately when the base snapshot is unavailable, while the notebook returns to the cleared Overview tab and disables project-derived tabs until a later successful refresh restores them. This prevents playback, timing, preview, and authoring layers from repopulating stale evidence or surfacing their own raw exception text after the base refresh has failed.

## Safety boundary

This changes presentation only. It does not alter source, mapping, timing,
arrangement, review, validation, export, packaging, or musical authority. No
live Rocksmith installation, NoCableLauncher, commercial audio, score, or DLC
content is touched.
