# Song Workspace background media loading

The packaged Windows Song Workspace must remain responsive while preparing normalized-audio preview state.

## Problem addressed

The original playback workspace called `load_or_build_waveform()` synchronously from `refresh()`. A cache miss hashes and iterates through the full normalized WAV before Tk can repaint or process input, which can make a multi-minute project appear frozen. Playback transport construction also revalidates the normalized WAV, so doing only the envelope loop in a worker would still leave avoidable full-file work on the event thread.

## Product contract

`ArrangementEditHistorySongWorkspaceWindow`, the final Song Workspace used by `cdlc-desktop`, starts waveform-cache loading and `ProjectAudioTransport` construction on a daemon worker.

- Tk refresh starts the worker and immediately returns.
- The status line explicitly reports that waveform/playback preparation is running in the background.
- Completed media state is marshalled back through Tk's deferred callback before widgets are updated.
- Each worker is bound to a monotonically increasing media-load generation and the exact resolved project path.
- Switching projects or destroying the workspace invalidates pending generations.
- A late worker result for an old project is discarded; its transport is closed rather than attached to the current workspace.
- Repeated refreshes do not start duplicate workers for the same project while one is already running.
- Missing or invalid normalized audio remains a non-authoritative preview failure and does not mutate musical, provenance, validation, export, package, or installation authority.

## Safety boundary

This change only affects local preview responsiveness. It does not change the normalized recording authority, shared timing authority, Bass/Lead/Rhythm review decisions, exports, or package safety. It never writes to the live Rocksmith installation or NoCableLauncher.

Tracked by issue #179 and the Product Reality performance/usability milestone.
