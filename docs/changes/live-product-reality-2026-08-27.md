# Packaged Product Reality — 2026-08-27

Tested Windows build: `v0.1.0 · d750567a`

Representative project: `Metallica - 03 For Whom the Bell Tolls (Remaster)`

## Confirmed working

- Song Workspace opens and reports 15/17 workflow steps complete.
- Timeline playback, stop, click/seek, horizontal song navigation, and mouse-wheel timeline zoom work.
- Reviewed shared Timeline / recording clock reaches the first substantial common instrument entrance at approximately `7.12 s`.
- Official TAB mapping dialog allows Bass, Lead, and Rhythm selection.

## Confirmed defects

### Official TAB image ingestion — issue #446

No tested TAB image could be registered. One ordinary `.jpeg` from the user's reference material was decoded by Pillow as `MPO` and rejected with:

`unsupported official TAB image format: MPO`

Because page ingestion failed, TAB page navigation, playback synchronization, role switching, and persistence tests were blocked.

Fix in the follow-up branch accepts JPEG-family `MPO` decoding for `.jpg` / `.jpeg` while preserving suffix/container validation and still rejecting MPO data presented as PNG.

### EOF reference controls unreachable — issue #445

The Timeline viewport ends at `Score-aware anchors` at 1920×1080. The horizontal scrollbar navigates the song and mouse wheel controls timeline zoom; there is no vertical page scroll that exposes the EOF panel appended below the base Timeline.

Fix in the follow-up branch moves the `Editor on Fire reference` panel to the leading edge of the Timeline so `Open in EOF`, `Compare alternate GP…`, and EOF evidence status are reachable without changing horizontal timeline navigation semantics.

### Residual symbolic timing projection — issue #431

The packaged retest still reproduces the existing residual timing blocker:

- reviewed Timeline / recording entrance: approximately `7.12 s`;
- Arrangement Preview first Bass/Lead/Rhythm symbolic events: approximately `11.77 s`;
- residual displacement: approximately `+4.65 s` late.

This is the same signature already tracked by #431 after the earlier EOF pre-roll and leading-rest fixes. The shared audio/beat clock is visibly healthy, so this result is logged as another failed packaged acceptance for #431 rather than a new duplicate defect.

No song-specific time shift is introduced in this follow-up. #431 remains open until the generic score-to-recording projection root cause is resolved and verified against EOF / a simpler control song.

## Next packaged acceptance

1. Register the same phone/camera `.jpeg` TAB page that previously reported `MPO`.
2. Register an ordinary JPEG and PNG.
3. Verify TAB page navigation, seek-to-page, role switching, and project reopen persistence.
4. Confirm the EOF reference panel is visible on Timeline at 1920×1080 and exercise `Open in EOF` / `Compare alternate GP…`.
5. Use EOF recording-clock evidence and a simpler fresh control song to continue #431 without compensating the correct shared beat grid.
