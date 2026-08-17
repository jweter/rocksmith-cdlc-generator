# Reviewed Bass authoring adapter

Issue #241 establishes promoted human-reviewed score timing as shared song timing for Bass, Lead, and Rhythm. The reviewed export projection now retains the selected source track's explicit tuning so downstream authoring consumers do not have to reopen an unbound source file to recover instrument identity.

`reviewed_bass_authoring_input()` is the first proving-path adapter between that reviewed projection and Rocksmith authoring. It is intentionally read-only. It returns Bass note timing using the promoted reviewed timestamps while preserving source-event identity, explicit string/fret positions, techniques, import confidence, source trust, score provenance, recording provenance, and fan-out provenance.

The adapter fails closed unless the arrangement is Bass, an explicit four-string tuning is present, every note has accepted symbolic/user-confirmed trust, no note still requires human review, every note has an explicit four-string position, and each string/fret position reproduces the source MIDI pitch under the retained tuning.

This slice does **not** write Rocksmith XML, rewrite canonical charts, alter `analysis/shared_timeline.json`, package CDLC, modify a Rocksmith installation, or infer missing musical information. Lead/Rhythm are deliberately not routed through this adapter because their current Rocksmith XML bridge requires preserved chord-group identity; flattening reviewed events into single notes would lose reviewed musical structure. A later slice should carry chord-group provenance explicitly before wiring reviewed Lead/Rhythm timing into XML authoring.
