# EOF fret-hand-position observation contract

The project now has a provenance-bound schema for manually reviewed Editor on Fire fret-hand-position markers. The contract is implemented in `rocksmith_cdlc_generator.eof_hand_position_observation` and is deliberately evidence-only.

Each fixture binds observations to an exact GP3/GP4/GP5 score SHA-256, source-track index, EOF version, and evidence note. Each marker records only the observed timestamp, displayed fret, and an optional source-event index. Observation times must be strictly increasing so the evidence record is deterministic and unambiguous.

`validate_eof_hand_position_fixture()` fails closed when the score hash or format is stale, the source track is no longer present, or an optional event reference no longer exists. Successful validation returns only an identity/count summary; it does not copy EOF state into the chart.

This contract intentionally does not define EOF's internal fret-hand-position algorithm, infer hand spans, choose preferred string/fret positions, score candidate fingerings, accept fingering/playability, rewrite imported notes, or alter validation/package readiness. Those behaviors require separate evidence and human-authorized design.

Lawful synthetic/public fixtures may be committed. Real-song observations derived from private or copyrighted project material must remain local/private unless redistribution rights are explicit. The pending packaged Bass Product Reality retest remains a separate human evidence lane and is not satisfied by this observation schema.
