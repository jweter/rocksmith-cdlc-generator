# BWV1007 staged printed-score recognition v2

## Product Reality trigger

The first real packaged Windows pass on BWV1007 Prelude page 2 exposed two independent failures in the original one-shot local vision recognizer:

1. an 8-measure pass could abort when `gemma3:4b` returned content that did not satisfy the structured response schema;
2. a 1-measure retry reached human review, but collapsed the dense first measure to five `string 0 / fret 0` notes even though the visible TAB contained a full sixteenth-note passage with multiple strings/frets.

The page/measure crop itself was visually usable, so this slice preserves the existing normalization and paired notation/TAB barline geometry and replaces the musical-recognition strategy.

## Recognition v2

`score_measure_recognition.py` now performs two independent local-only vision passes per measure:

1. **TAB pass** — sends only the lower TAB band and asks for every printed fret token, string index, and normalized horizontal position. It does not ask the model to infer rhythm.
2. **Notation pass** — sends only the upper standard-notation band and asks for every note/rest, beat, duration, optional notation pitch, techniques, and normalized horizontal position. It does not ask for string/fret.
3. **Reconciliation** — note events are matched in left-to-right order and cross-checked by horizontal position. TAB supplies string/fret; notation supplies rhythm. The existing pitch check compares TAB-derived MIDI against optional notation MIDI.

The recognizer version is now `2`. Candidate/review artifact shape remains compatible with the existing human-review UI.

## Fail-closed behavior

A TAB/notation sounded-note-count mismatch triggers one notation recheck using the independently observed TAB token count as a cross-check. If the counts still disagree, the measure fails with an explicit measure-numbered error instead of emitting a sparse false transcription.

Every candidate remains `review_required=true`; local model output never becomes musical authority without the existing human review gate.

## Structured-output recovery

A single full JSON Markdown fence is accepted as harmless transport formatting. Genuine Pydantic/schema failure is retried once with a stricter schema-only instruction. If the retry also fails, the error identifies the exact measure/stage and reports only a sanitized validation summary; private score content is not logged.

## Desktop progress

The packaged desktop now receives recognition progress updates and changes the current-task line through stages such as:

- page segmentation;
- `Measure N of M: reading TAB fret tokens`;
- TAB token count;
- notation rhythm pass;
- note-count recheck when required;
- reconciliation;
- candidate save/completion.

This does not yet add cancellation or a periodic heartbeat while one blocking Ollama request is in flight, but it removes the previous all-or-nothing `starting` display between measures.

## Regression coverage

`tests/test_score_measure_recognition.py` now covers:

- separate TAB and notation image/schema calls;
- a synthetic dense 16-sixteenth-note measure preserving all 16 fret tokens;
- fenced valid JSON;
- malformed response retry success and retry exhaustion;
- fail-closed TAB/notation note-count mismatch with notation recheck;
- loopback-only private-image transport;
- TAB/notation pitch mismatch reporting;
- unchanged human-review authority boundary.

## Next laptop acceptance pass

Use the existing registered BWV1007 Prelude project. Start with **page 2 / one measure / `gemma3:4b` / five systems**. The first measure should either show the full dense note sequence in Review or fail with a specific TAB-vs-notation count/schema error. Do not expand to eight measures until measure 1 is materially correct.

Refs #508, #509, #511.
