# Live Product Reality diagnostics

Packaged Product Reality testing needs to reveal more than hard crashes. A workflow can be slow, waiting on human authority, recover from a warning, or reject stale state correctly without the application terminating. Those events must be observable while the representative song is being authored.

The primary guided desktop therefore includes an always-visible **Live diagnostics** panel. It mirrors the most recent operational messages while the existing **Activity Log** remains the full in-session history. Entries are timestamped and classified as informational, warning, or error diagnostics where practical.

The guided desktop also persists local diagnostic entries to `review/desktop_diagnostics.jsonl`. This file is generated project evidence and remains outside source control. It records operational text only. It must not contain audio bytes, score contents, Ubisoft-derived content, credentials, or other commercial media. Persisted timestamps are stored in UTC and converted back to the desktop's local timezone when displayed so reopened history remains chronologically comparable with new live entries. Malformed or boundary timestamps fail closed to an unknown clock display rather than interrupting project opening.

Long-running Bass transcription already publishes `automatic_task_status.json` and `automatic_task_log.jsonl`; progress transitions from that worker continue to flow through the desktop logger, so chunk progress appears in both the full Activity Log and the visible diagnostic panel. Background operation starts, completions, failures, traceback diagnostics, project-open events, and meaningful workflow-state changes are also visible during testing.

Diagnostic project lifecycle events are project-scoped. A `Project opened` event is recorded only after the requested manifest actually loads successfully; retaining a previously selected path after a failed same-project reload is not treated as success. Workflow-state deduplication includes project identity so switching between two projects with the same readiness text still records each project's initial state.

Diagnostic persistence is deliberately best-effort. A logging write failure is ignored and cannot change workflow state, satisfy a review gate, fail a valid authoring action, or become an authority source. Existing human review boundaries for source rights, score mapping, timing, musical corrections, tone decisions, source acceptance, and packaging remain unchanged.
