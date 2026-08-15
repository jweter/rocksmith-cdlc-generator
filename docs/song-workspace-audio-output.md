# Song Workspace audio output selection

The packaged Windows Song Workspace exposes the local preview output device used by the optional `sounddevice` playback runtime.

## Behavior

- Only endpoints that report one or more output channels are shown.
- The current Windows/default output is identified explicitly.
- A user-selected output is applied to the application-wide `sounddevice` default and persisted under the local application settings directory as endpoint index + name metadata only.
- On a later launch, the saved endpoint is matched by exact index/name first and then by name so normal Windows device-index reordering does not silently move preview audio to another device.
- If the saved device is absent, the current Windows/default output is used instead.
- Changing output closes/recreates local preview media so an already-open `RawOutputStream` cannot remain attached to the previous endpoint.
- The Diagnostics action lists output-capable devices, channel counts, default sample rates, and the Windows/default endpoint.

## Authority and privacy boundary

Audio-output selection controls local monitoring only. It does not modify normalized project audio, recording identity, score data, shared timing authority, Bass/Lead/Rhythm notes, positions, techniques, fingering, chord identity, validation, export/package readiness, or PSARC registration.

The persisted preference contains no project path, media bytes, score bytes, CFSM data, Ubisoft-derived content, or other private project artifacts. The application still never writes to the live Rocksmith installation or NoCableLauncher.
