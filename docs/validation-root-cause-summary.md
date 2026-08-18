# Validation root-cause summary

A Product Reality run showed that validation can emit dozens or hundreds of findings with the same underlying cause. Listing every finding in the human-facing Markdown summary makes one systemic problem look like many independent decisions and hides the highest-value corrective action.

`validation.py` now groups the human-facing `review/summary.md` by exact `(severity, stage, code)` root cause. Repeated findings show their occurrence count, the first affected time when available, and one representative message. Deterministic ordering still prioritizes the highest-priority findings first.

This is a presentation-only aggregation. `review/validation_report.json` and `review/flags.json` continue to retain every individual review item with its original message, time, note index, priority, and severity. Validation status, failure/warning counts, packaging authority, and every human review requirement are unchanged.

The grouping key intentionally does not infer semantic equivalence between different validation codes. Distinct codes remain distinct even when their messages appear similar; this keeps the summary fail-closed and avoids merging unrelated musical, timing, mapping, reconciliation, or authoring problems.

Safety boundaries remain unchanged: this feature does not resolve findings, accept source or musical decisions, alter notes/timing/fingering/techniques, promote Rocksmith XML, package CDLC, modify the live Rocksmith installation, or interact with NoCableLauncher. No commercial media/DLC, private CFSM exports, Ubisoft-derived content, or generated private project data is committed.
