# Issues #445 / #446 — packaged live-test fixes

This change set addresses two hard blockers found in Windows packaged build `d750567a`.

## #445 — EOF controls clipped below Timeline

The base Timeline expands to consume the available viewport. `EOFWorkspaceMixin` previously appended its reference panel after that content, leaving `Open in EOF`, `Compare alternate GP…`, and EOF evidence statuses below the visible 1920×1080 viewport with no vertical page scrolling.

The EOF reference panel is now packed before the existing Timeline children. Timeline horizontal navigation and zoom behavior are unchanged; the external-reference controls are visible without depending on an unavailable vertical page scroll.

## #446 — phone/camera JPEG reported as MPO

The Official TAB validator previously accepted only Pillow formats `JPEG` and `PNG`. Some valid `.jpg` / `.jpeg` images, especially phone/camera images, are decoded by Pillow as `MPO` because the JPEG container includes multiple-picture metadata.

Validation now uses a suffix-aware format allow-list:

- `.jpg`, `.jpeg`: `JPEG` or `MPO`;
- `.png`: `PNG` only.

For MPO-backed JPEGs, frame 0 is explicitly selected and verified. The viewer already converts the opened page to RGB, so this preserves the intended single-page reference behavior without treating additional MPO frames as musical or reference authority.

Regression coverage verifies that `.jpeg` accepts an MPO decoder result while `.png` still rejects it.

## Timing note

The same packaged session reconfirmed issue #431: the shared recording Timeline reaches the real first common entrance near `7.12 s`, while Arrangement Preview remains near `11.77 s`. That is logged against #431 and is intentionally not papered over with a song-specific offset in this UI/image fix.
