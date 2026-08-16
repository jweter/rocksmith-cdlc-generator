# Product Reality responsiveness boundary

The first packaged Product Reality Gate run exposed a normal-path freeze while generating the audio-derived Bass draft for a full-length song. The desktop workflow was already dispatched from Tk onto a Python background thread, so the corrective boundary is stronger than simply adding threading.

## Packaged Bass transcription

`librosa.pyin` is CPU/GIL-heavy enough that executing it inside the packaged GUI process can starve Tk event processing even when invoked from a background thread. In the packaged Windows application, the planner-owned `cdlc transcribe-bass` command therefore re-enters `RocksmithCDLCGenerator.exe` in a private worker mode and performs transcription in that child process.

The parent GUI process remains responsible for workflow state, busy-state presentation, completion/failure handling, and refresh. The child receives only the existing closed planner argv accepted by `desktop_command_runner`; no shell or arbitrary executable dispatch is introduced.

The worker also writes a short-lived structured result file in the system temporary directory. Success includes the deterministic return code. Failure includes the exception type, message, and traceback. The parent deletes that temporary IPC file after reading it and raises worker failures through the existing desktop background-error path, so a failed packaged transcription cannot be misreported as a successful return to `Ready`.

A second Product Reality run showed that process isolation alone was insufficient for a full-length representative song. Bass pYIN analysis is therefore resource-bounded as well: the normalized recording is analyzed in fixed-duration core chunks with overlapping context. Core intervals partition the recording exactly once, while overlap is analysis context only. A detected note is retained only by the chunk whose core interval owns that note onset, preventing silent duplication at chunk boundaries.

## Live task observability

Long-running Bass analysis publishes a media-free task status artifact under the project review directory plus a compact JSON-lines task log. The guided desktop polls that status while automatic work is active and displays:

- the current automatic task;
- the current analysis stage/chunk;
- percent complete;
- elapsed time;
- age of the last progress update.

Progress transitions are also mirrored into the existing Activity Log. This is diagnostic state only: it contains no audio, score contents, or commercial media bytes and does not change workflow authority.

Development and ordinary Python test execution retain the in-process dispatcher. The process isolation applies only to a frozen packaged executable and only to Bass transcription at this stage; chunked pYIN behavior is shared so long-song resource bounds are consistent across packaged and development execution.

## Safety boundaries

This responsiveness fix does not change musical or provenance authority:

- source rights and score mappings remain human-confirmed;
- the workflow planner still decides whether Bass transcription is eligible to run;
- worker isolation and chunking do not auto-accept transcription confidence or downstream review gates;
- no live Rocksmith installation or NoCableLauncher path is touched;
- generated/private project data remains local and gitignored;
- worker IPC contains diagnostics only and is removed by the parent after each run;
- persistent task status/log artifacts contain operational diagnostics only, not private media content.

Regression tests verify process delegation/error propagation, deterministic chunk ownership, progress reporting, task-status persistence, and that non-packaged execution preserves the existing closed dispatcher behavior.
