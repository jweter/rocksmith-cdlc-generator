# Project-required action guidance (#304 / #305)

## Product symptom

Several always-visible desktop actions silently returned when no project was
open:

- Open Project Folder;
- Confirm Bass/Lead/Rhythm Mapping;
- Record Human Review.

Register Score and Run Next Steps handled the same empty state differently by
showing a recovery notice. The inconsistency made some controls appear broken
and forced a user to infer why nothing happened.

## Resolution

The base desktop shell now uses one `_require_project()` guard for all five
project-bound actions. When no project is open, each action shows the same
owned notice: **Open or create a project first.** When a project is open, the
helper returns its path without displaying anything.

This is an empty-state and recovery-guidance change only. It does not create a
project implicitly or bypass any rights, mapping, timing, validation, or
packaging gate.

## Regression protection

`tests/test_desktop_project_required_actions.py` verifies both helper states
and requires every visible project-bound action to use the shared guard.
