# Product Reality responsiveness boundary

The first packaged Product Reality Gate run exposed a normal-path freeze while generating the audio-derived Bass draft for a full-length song. The desktop workflow was already dispatched from Tk onto a Python background thread, so the corrective boundary is stronger than simply adding threading.

## Packaged Bass transcription

`librosa.pyin` is CPU/GIL-heavy enough that executing it inside the packaged GUI process can starve Tk event processing even when invoked from a background thread. In the packaged Windows application, the planner-owned `cdlc transcribe-bass` command therefore re-enters `RocksmithCDLCGenerator.exe` in a private worker mode and performs transcription in that child process.

The parent GUI process remains responsible for workflow state, busy-state presentation, completion/failure handling, and refresh. The child receives only the existing closed planner argv accepted by `desktop_command_runner`; no shell or arbitrary executable dispatch is introduced.

Development and ordinary Python test execution retain the in-process dispatcher. The process isolation applies only to a frozen packaged executable and only to Bass transcription at this stage.

## Safety boundaries

This responsiveness fix does not change musical or provenance authority:

- source rights and score mappings remain human-confirmed;
- the workflow planner still decides whether Bass transcription is eligible to run;
- worker isolation does not auto-accept transcription confidence or downstream review gates;
- no live Rocksmith installation or NoCableLauncher path is touched;
- generated/private project data remains local and gitignored.

Regression tests verify that the packaged parent delegates Bass transcription to the worker, that worker mode does not recurse into another child process, and that non-packaged execution preserves the existing in-process behavior.
