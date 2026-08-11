# ADR-033: Human-approved Rocksmith tone review artifacts

## Status

Accepted.

## Context

The generator can now map researched tone/effect evidence to abstract Rocksmith tone families and then bind those families to real Rocksmith 2014 device keys from a catalog derived locally from the user's own Rocksmith installation.

That binding is still not sufficient evidence for automatic packaging. Catalog matching is semantic and deterministic, but a similarly named Rocksmith device is not proof that it is the correct musical approximation. Default knob values are likewise not evidence for the recorded tone.

## Decision

Introduce a separate, schema-versioned human-review artifact between catalog binding and DLC Builder tone injection.

The artifact records:

- artist/title identity,
- exact tone-catalog SHA-256,
- exact bound-plan SHA-256,
- arrangement and tone label,
- every selected Rocksmith device key and slot,
- editable knob values,
- per-component approval state,
- per-tone approval state,
- reviewer notes,
- a derived `ready_for_injection` flag.

A component cannot be approved while its device key or Rocksmith slot is unresolved. A tone cannot be approved until every component is approved. The whole artifact becomes ready for injection only when every tone is approved.

Before any future injection step consumes an approval artifact, it must verify that both the catalog SHA-256 and bound-plan SHA-256 still match the current inputs. Any changed device binding or knob baseline invalidates the old approval.

## Consequences

- Generated tone recommendations remain easy to review and edit without weakening provenance.
- The future GUI can expose the same artifact directly as an approval panel.
- Stale approval cannot silently authorize a changed tone plan.
- Automatic tone injection remains prohibited until a later ADR defines the exact reviewed `Tone2014` serialization into the DLC Builder project and validates it on a real package.

## Next

1. Import a real locally generated Rocksmith 2014 device catalog.
2. Create and review real Lead/Rhythm/Bass tone artifacts.
3. Add reviewed `Tone2014` serialization using only `ready_for_injection=true` artifacts.
4. Verify generated tones through DLC Builder and a deliberately staged Rocksmith package before broad automation.
