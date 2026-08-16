# Desktop XML export state correction

The validation-gated desktop XML exporter must report only operations that were actually accepted and results that still belong to the currently open project.

## Correctness contract

- A request rejected because another desktop background operation is active is not shown as running.
- An accepted export that fails validation or raises another exporter error leaves the arrangement row in an explicit failed state rather than a permanent running state.
- Success and failure callbacks are bound to the project that originated the export. If the user changes projects before completion, the stale callback is ignored and cannot overwrite the new project's UI state.
- The existing authoritative arrangement validation/export gate remains unchanged; this correction adds no new musical, tone, source, packaging, or installation authority.

The desktop background runner now returns whether work was accepted and supports an optional failure callback after the existing generic error handling. This keeps the XML window synchronized with the real operation lifecycle without queueing hidden work or weakening any fail-closed gate.
