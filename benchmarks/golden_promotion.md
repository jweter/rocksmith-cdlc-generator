# Golden benchmark promotion

A candidate is not a trusted benchmark merely because structured notation exists. Promotion is an explicit, metadata-only gate represented by `BenchmarkPromotionRecord`.

A record is ready only when all of the following are true:

- the current Rocksmith/CFSM library has been checked deterministically and the song is absent;
- a lawful local audio source is available;
- a lawful structured reference or deliberate human-authored reference is available;
- a human has reviewed and accepted the reference chart;
- a representative 30–90 second excerpt has been selected;
- provenance has been recorded.

The promotion record stores no commercial media bytes and no local source paths. It deliberately forbids extra fields so location-bearing source metadata cannot be added casually. Source availability never substitutes for human acceptance.

The candidate-bank tiers remain the progression order: Tier 1 establishes the MVP corpus, Tier 2 tests generalization, Tier 3 adds advanced arrangements, and Tier 4 is reserved for stress testing. Promotion is evaluated per candidate rather than granting trust to a whole tier at once.
