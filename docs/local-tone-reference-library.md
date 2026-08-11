# Local Tone Reference Library

This document defines the private reference corpus built from Rocksmith packages already installed on the user's machine.

## Goal
Use real Rocksmith tone configurations as empirical starting points for new CDLC tones instead of synthesizing amp/effect chains and knob values blindly.

## Data flow

```text
local Rocksmith DLC directory
        ↓
read-only PSARC discovery
        ↓
new/changed package detection
        ↓
local PSARC tone extraction
        ↓
normalized Lead/Rhythm/Bass tone records
        ↓
private tone_reference_library.json
        ↓
reference similarity ranking
        ↓
research + audio analysis + human review
        ↓
approved new Rocksmith tone
```

## Local-only rule
The scanner operates only on paths explicitly selected by the user. It does not download DLC, upload packages, or modify the Rocksmith installation. The generated library is private derived data and should live under an ignored local/private directory.

## Reference records
Each extracted tone should retain:

- package SHA-256 and path provenance;
- official/custom/user/unknown source classification;
- artist, title, album when present;
- Lead/Rhythm/Bass arrangement role;
- tone name/key/descriptors/volume;
- Amp/Cabinet/PrePedal/PostPedal/Rack slots;
- Rocksmith device keys and names;
- exact knob values present in the package;
- tone-change timestamps;
- deterministic tone fingerprint.

## Ranking policy
Official Rocksmith tones receive the strongest prior authority. Community CDLC remains useful as a larger secondary corpus but is never assumed to be correct merely because it packages successfully.

Initial similarity uses arrangement role, device overlap, descriptors, and authority. Later iterations should add signal-chain topology, knob-distance metrics, section/use labels, researched real-world rig similarity, and audio-derived tone/effect features.

## Incremental scanning
Large DLC collections should be inexpensive to refresh. The scan planner compares path, size, and modification time and only schedules new or changed packages for extraction. The expensive extraction step records a full SHA-256. Deleted packages disappear from the active derived index.

## Planned GUI integration
The future Song Workspace should expose reference matching in the tone review panel:

- suggested tone and confidence;
- closest official Rocksmith references;
- closest community references separately;
- common amp/effect chain;
- knob ranges/median values across similar references;
- source song/arrangement labels;
- preview, alternate selection, edit, and approve actions.

The reference library is advisory. A reference match never bypasses the human tone approval gate.