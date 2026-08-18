# Warning category summary

A real multi-arrangement Product Reality run showed that even after repeated validation findings are grouped by exact root cause, the human-facing review can still contain a warning flood spread across several detailed codes. The first question for triage is often broader: which validation category is producing the pressure?

`validation.py` now adds a read-only **Warning Categories** section to `review/summary.md`. Warning items are grouped by their existing validation `stage`, with the total warning count and the exact distinct warning codes listed for each category. Categories are ordered by their highest contained review priority, then by warning volume and stage name.

This is presentation-only. It does not change `ValidationReport.warning_count`, warning severity, priority, packaging eligibility, or any individual `ReviewItem`. The complete warnings remain in the detailed root-cause section, `validation_report.json`, and `flags.json`.

The category summary grants no review authority. It does not accept or resolve source, timing, fingering, chord, technique, tone, mapping, or reconciliation decisions. It does not write Rocksmith XML, package CDLC, modify a live Rocksmith installation, or interact with NoCableLauncher. No commercial audio/DLC, private CFSM exports, generated private project data, Ubisoft-derived content, or PSARC packages are committed.

This addresses the warning-flood Product Reality finding recorded in issue #268 while preserving every existing fail-closed validation and human-review boundary.
