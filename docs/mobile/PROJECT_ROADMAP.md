# Rocksmith Pocket Workshop — New Mobile Project Charter

**Planning status:** proposed separate iOS product track; **not** a current executable iOS app, installed service, or owner runtime-mode change. 2026-11-01.

**Parent project:** [Rocksmith CDLC Generator](https://github.com/jweter/rocksmith-cdlc-generator)  
**Product form:** Offline guitar/bass arrangement editor and audio analysis, with optional desktop packaging  
**Project ID:** `rocksmith_workshop`

## Vision and product promise

Create a musician-first iPhone studio for offline song import, waveform/tempo inspection, bass/lead/rhythm tablature, fret/string mapping, timing adjustment and honest validation/export. Explore a completely on-device arrangement generation pipeline without assuming the existing Windows/.NET PSARC packaging dependencies can ship in an iOS app.

## Current verified foundation

The existing tool is Python 3.12+ on Windows 11 and depends on FFmpeg/ffprobe, optional transcription/separation, and a .NET 10 PSARC bridge; final game-compatible packaging is delegated to DLC Builder / Rocksmith2014.NET. These desktop steps are not already native iOS frameworks. The existing normalized WAV + provenance + validated arrangement outputs provide good portable interchange targets.

## First real user journey

In airplane mode, import a legally held local audio file, inspect its waveform and detected tempo, tap a beat to correct it, author or edit bass/lead/rhythm notes on an iPhone fretboard/timeline, preview alignment, run instrument-specific validation, then export a self-contained project bundle, MusicXML or MIDI without desktop software.

## Non-negotiable standalone contract

- Files audio import, format validation and hashes; AVFoundation/Accelerate waveform and onset/tempo computation at bounded size.
- Offline manual tablature editor with bass/lead/rhythm as first-class instruments, undo/redo and timing calibration.
- Deterministic note/fret feasibility validation and honest export to standard non-PSARC interchange formats plus project manifest.
- No network, Spotify/YouTube DRM bypass, remote audio processing or server required for core authoring.

## Optional connected expansion (not a dependency)

Opt-in desktop pipeline for high-compute stem separation/transcription and actual Rocksmith 2014 package build. Future standalone on-device stem/transcription and PSARC construction require real-device performance/licensing validation, reproducible artifact tests, and a verified real in-game import; not a v1 promise.

## Out of scope and honest feasibility boundary

The standalone v1 is a real and useful arrangement workstation, not automatically a fully device-made playable Rocksmith CDLC package. Treat in-game PSARC packaging as an explicit high-risk research gate.

## Portfolio operating principles

- Phone-first: app launches and performs its declared MVP value in airplane mode without Azathoth, GitHub, a hosted API, or a paid service.
- Native-first for the long run; a PWA or companion prototype may validate UX sooner, but may not be represented as proof of fully native offline functionality.
- One source of product truth: share formats, algorithms and fixtures with parent project; never fork the entire Python/Windows backend or invent duplicate business rules.
- Optional sync must be explicit, authenticated, revocable and resilient to disconnection; an offline session must never trigger an implicit network request.
- Protect user data: use iOS sandbox, Files integration, file protection/Keychain for secrets; avoid collecting unnecessary user content and telemetry.
- Keep parent project quality policies: narrow branches, exact-head tests, licensing/provenance checks, review and product reality. Do not install or alter the running Iron God release.
- Measure device performance, memory, thermals and battery on physical supported iPhones; record actual evidence before making capability or compatibility claims.
- Maintain accessibility (VoiceOver, Dynamic Type where applicable, contrast, touch targets), cancel/resume behavior and storage bounds.
- No Apple membership purchase, Mac rental, new paid service, signing certificate or public App Store distribution without separate explicit owner decision.

## Build environment and cost constraints

Native iOS signing, on-device testing and App Store submission normally require macOS/Xcode infrastructure; the Windows laptop can remain the source-development and test workstation. Start with portable C++/Swift contract fixtures and SwiftUI design prototypes where a Mac runner/device is not yet available. Personal device development can start without paid Apple Developer Program membership, subject to Apple's provisioning limits; App Store/TestFlight distribution requires program enrollment.

Default cost target $0 before owner-approved developer membership, build-machine access or cloud usage. Keep optional model downloads, paid APIs, hosted inference and other recurring costs opt-in. No automatic spending.

## Parent-code and platform references

- https://github.com/jweter/rocksmith-cdlc-generator/blob/main/README.md
- https://github.com/jweter/rocksmith-cdlc-generator/blob/main/PROJECT_PLAN.md


---

# Rocksmith Pocket Workshop — Phased iPhone Roadmap

**Status:** PLANNED. Phases are evidence gates, **not calendar commitments**. Parent projects retain authority over their existing implementation and product quality.

## Release strategy

Start by proving a no-server/no-laptop local user journey. Give native/local capabilities their own implementation and acceptance tests. Add external integrations only after the standalone core works. For every phase: maintain a narrow branch, exact-head tests, real device evidence and explicit limitations; do not call draft prototypes complete.

## P0 — Format and feasibility mapping

**Deliverables**

- Inventory parent normalized audio, tempo, arrangement XML, source manifest and DLC Builder packaging boundaries.
- Choose portable project and note interchange schema; verify license restrictions for audio/codec/native libraries.
- Profile one real iPhone audio import and simple tempo detector using a representative legal sample.

**Exit gate:** Portable fixture round trip established; irreversible/Windows packaging gap recorded explicitly.

## P1 — Offline audio and tab notebook

**Deliverables**

- Build native local import, waveform, grid, metronome and editable Lead/Rhythm/Bass tracks.
- Implement bounded project store, undo, time offset/tempo adjustment and private export.
- Add sample-accurate position tests and accessible editing alternatives.

**Exit gate:** Record/import audio, edit a small bass arrangement and reopen/export offline from a real iPhone.

## P2 — Arrangement validation and interchange

**Deliverables**

- Port deterministic fret/string/timing/technique validation with shared parent fixtures; classify PASS/WARNING/FAIL without overstating playability.
- Export standard MIDI, MusicXML and generator-native project manifests as supported; test round trips.
- Enable a clean desktop importer for optional later packaging.

**Exit gate:** An exported edit reimports with note/time/fingerings preserved; no claim that this is a playable PSARC.

## P3 — On-device assistant experiments

**Deliverables**

- Evaluate only permitted local tempo/stem/note estimation models on one target iPhone; constrain CPU, model size and heat.
- Allow a musician to review and correct confidence-ranked suggestions; never silently replace manual notation.
- Compare real sample accuracy to approved fixtures before enabling any ML-based auto-arrange.

**Exit gate:** A representative real song excerpt produces useful, verifiable suggestions locally or the feature stays experimental.

## P4 — Game packaging feasibility decision

**Deliverables**

- Investigate whether legal portable PSARC/WEM/SNG packaging and game-compatible metadata can be implemented on iOS without prohibited third-party dependencies.
- If feasible, build an isolated native package and prove it imports/runs in actual Rocksmith; otherwise keep a clean optional Windows handoff.
- Capture precise quality, license and Product Reality evidence before changing roadmap scope.

**Exit gate:** Either reproducible real in-game compatible offline packaging is demonstrated, or a documented blocker/fallback prevents false shipping claims.

## P5 — Native beta

**Deliverables**

- Profile audio latency, background playback, file imports and phone-screen tab ergonomics.
- Check content rights, local data privacy, codecs/library attribution and Store distribution constraints.
- Perform physical-instrument musician review and representative song round trip.

**Exit gate:** Offline song-to-arrangement project workflow works on device; packaging status is correctly represented.

## First independently actionable engineering slices

1. RSP-001: prove interchange with existing normalized audio/project and arrangement fixtures
2. RSP-002: native WAV/audio import + tempo/waveform device benchmark
3. RSP-003: touch fretboard/tab authoring with undo and three instrument classes
4. RSP-004: deterministic arrangement-validation and MIDI/MusicXML round trip
5. RSP-005: native packaging legal/technical feasibility investigation

## External blockers / decisions held for later

The standalone v1 is a real and useful arrangement workstation, not automatically a fully device-made playable Rocksmith CDLC package. Treat in-game PSARC packaging as an explicit high-risk research gate.

Open decisions to defer: name/icon/branding; minimum iOS version and target devices after a build smoke; distribution model and monetization; Apple signing infrastructure; optional online sync; optional on-device inference models. None block offline planning and portable-contract work.

## Change-control and roadmap hygiene

This iOS roadmap is a distinct **proposal** and does not silently expand the owner-approved desktop implementation roadmap. On approval of a phase, add narrowly bounded capability graph entries or planning issues in the appropriate development project; do not auto-enroll these proposals in the active Iron God production dispatcher, grant runtime execution rights, or compete with its owner/session control. Cross-repo dependencies must reference the specific parent schema/commit and explicit acceptance evidence. Record verified milestone outcomes, not guesses.


---

# Rocksmith Pocket Workshop — Architecture, Risks and Validation

## System components and reuse seams

- `PocketAudioAnalysis` AVFoundation/Accelerate, waveform/downsampling/tempo, user annotations and source SHA.
- `ArrangementModel` portable Lead/Rhythm/Bass notes/techniques/fingerings/timing schema compatible with desktop generator fixtures.
- `TabEditor` SwiftUI timeline and fretboard; `ValidationEngine` portable deterministic music checks; `Export` local project/MIDI/MusicXML (where schema supported).
- `OptionalDesktopBuilder` explicit authenticated handoff to existing Windows DLC Builder/PSARC bridge, without writing to live Rocksmith installation.

## Offline / optional-online data flow

**Offline:** Files / mic / touch input → local validated parser → versioned local store → deterministic logic and (if proven) on-device inference → local UI / Files export. No remote call is necessary for the core workflow.

**Online enhancement:** explicit user action → permission/identity check → versioned optional adapter → external backend or online public source → source/receipt validation → local persisted result. Network failure leaves the offline product functional; remote-only operations fail visibly and never impersonate local results.

## Technical and delivery risks

- **Final DLC packaging:** Windows .NET/DLC Builder is a real dependency; cannot assert fully on-device Rocksmith-compatible PSARC until separately proven.
- **Copyright:** Require rights to user-provided audio and avoid bundling commercial copyrighted songs or protected content.
- **Heavy separation models:** Stem separation and polyphonic transcription may exceed mobile performance; require benchmarks and confidence/quality evidence.
- **Timing correctness:** Sample rate transforms and tempo grids must preserve millisecond/note alignment across exports.

## Cross-cutting real-device acceptance matrix

1. Fresh install + airplane mode + Azathoth completely off: app launches and completes the documented core user journey without stalls or hidden remote services.
2. Cold start, memory peak, battery/thermal behavior, model/download size and task latency measured on an actual physical device. Set release budgets from the first spike rather than inventing benchmark successes.
3. No unauthenticated inbound listening port, leaked token, bundled source secret, plaintext private sync credential or surprise upload; perform negative network test.
4. App returns a visible failure state when inputs, permissions, local model assets or Files permissions are missing. No fabricated output or false completion.
5. User can export, back up and delete locally created work without a server; app survives force quit and offline relaunch without losing completed edits.
6. Cross-platform contract/fixture tests verify imported/exported formats against the parent repository; snapshots are not treated as live or authoritative.
7. Standard automated checks, independent review, privacy/permissions declarations, App Store licensing/provenance review and actual iPhone product test must pass before external beta.

## Release evidence template

- Exact source head and build identity; Xcode/SDK/device/OS and model/runtime version if used.
- Recorded airplane-mode test with desktop/server powered off, input fixtures, expected outputs, pass/fail and timings.
- Memory/CPU/battery/thermal/storage measurements; accessible UI screen review; interruption/resume evidence.
- Data privacy/security review, license inventory, signed-build provenance, reviewer approval and open blocker list.
- Explicit distinction: proposed concept vs prototype vs device-proven vs App Store distributable.

## References

- https://github.com/jweter/rocksmith-cdlc-generator/blob/main/README.md
- https://github.com/jweter/rocksmith-cdlc-generator/blob/main/PROJECT_PLAN.md
