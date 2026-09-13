# Private Product Reality Runner — implementation notes

This file is intentionally narrow and accompanies #612.

The runner should be implemented as a deterministic engine under the existing CLI, not as GUI-only behavior. The GUI/launcher may invoke it later.

Initial dependencies should be existing project models/readers only. Do not add a model/AI dependency to determine timing PASS/FAIL.

The first scenario should consume current generated authority artifacts rather than re-running the whole pipeline. This makes the runner fast, repeatable, and useful after every build.

Future orchestration can add a `--rebuild`/launcher mode that first runs safe automatic generation and then evaluates the same evidence contract.
