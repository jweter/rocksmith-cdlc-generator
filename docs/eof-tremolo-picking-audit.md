# EOF tremolo-picking audit

Issue context: #414 / #455

## Scope

This is a provenance-safe reference audit for the EOF parity program. It does not change musical output, infer Product Reality, or import upstream source code.

## Evidence inspected

- Current `raynebc/editor-on-fire` source search at commit `4a724f4b068b4dd11a71a4b688707a0ed35b6563` returns tremolo-related behavior across the mature editor/export codebase.
- The local parity matrix currently marks **Tremolo picking** as `UNASSESSED`, P1, with the exit condition to include phrase-boundary behavior where required.
- The Rocksmith generator already contains tremolo-related concepts elsewhere, so the next implementation decision must distinguish GP import semantics from Rocksmith XML/export semantics rather than treating the word `tremolo` as one interchangeable flag.

## Audit conclusion

The safe next step is **not** to auto-map every GP tremolo-like field directly into a Rocksmith note attribute. The parity lane needs a field-by-field trace first:

1. Identify the exact Guitar Pro source field(s) decoded by PyGuitarPro for tremolo picking and any beat-level duration/rate information.
2. Trace EOF's GP import handling for those fields at a pinned upstream commit and record whether EOF stores, transforms, or discards them.
3. Separately trace EOF's Rocksmith export representation and any phrase/section boundary constraints.
4. Compare those semantics with this project's existing `guitarpro_import.py`, reviewed-technique authority, and `rocksmith_xml.py` export model for Bass, Lead, and Rhythm.
5. Only then implement the smallest lossless mapping. Ambiguous or non-lossless cases must continue to fail closed into human review rather than inventing technique data.

## Safety / provenance boundary

- No commercial audio, score pages, private GP files, Ubisoft-derived restricted content, or generated private workspaces are used here.
- Upstream EOF is used as behavioral/reference evidence only in this audit; no source is copied.
- Human Product Reality remains required for final musical acceptance.

## Verification target for the implementation follow-up

A future implementation slice should add synthetic regression fixtures proving the exact GP field-to-internal-technique mapping, Bass/Lead/Rhythm preservation, Rocksmith XML output semantics, and fail-closed behavior for unsupported/ambiguous variants. Packaged Windows/gameplay acceptance remains separate Product Reality debt.
