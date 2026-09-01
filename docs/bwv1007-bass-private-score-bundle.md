# BWV 1007 Bass Private Score Bundle

## Purpose

This document records the first complete multi-page printed-notation/TAB source set intended for the project's **Printed Notation / TAB Practice Mode**.

The source is:

- **Work:** Johann Sebastian Bach — *Cello Suite No. 1 in G Major, BWV 1007*
- **Book:** *Bach Cello Suites for Electric Bass*
- **Arrangement:** Matt Scharfglass
- **Publisher:** Hal Leonard Corporation
- **Copyright:** 2014
- **ISBN:** 978-1-4803-6186-7
- **Instrument:** 4-string electric bass
- **Tuning:** Drop D, low-to-high D-A-D-G (`[38, 45, 50, 55]` MIDI)
- **Source class:** user-owned local printed score

The copyrighted photographs/scans are **private local evidence**. They are intentionally not stored in this public Git repository.

The repository stores only the public-safe metadata manifest:

```text
benchmarks/private_reference_sets/bwv1007_bass_dropd.yaml
```

That manifest contains page ordering, capture hashes, movement boundaries, tuning, bibliographic metadata, and notation-legend vocabulary. It does not contain the printed music itself.

## Captured source set

The bundle contains 15 private images:

| Local image | Printed page | Kind | Purpose |
|---|---:|---|---|
| `IMG_4401.jpeg` | — | contents | Book contents/front matter |
| `IMG_4388.jpeg` | 2 | score | Prelude begins; Drop D tuning statement |
| `IMG_4389.jpeg` | 3 | score | Suite score |
| `IMG_4390.jpeg` | 4 | score | Suite score |
| `IMG_4391.jpeg` | 5 | score | Prelude → Allemande boundary |
| `IMG_4392.jpeg` | 6 | score | Allemande |
| `IMG_4393.jpeg` | 7 | score | Allemande |
| `IMG_4394.jpeg` | 8 | score | Allemande → Courante boundary |
| `IMG_4395.jpeg` | 9 | score | Courante |
| `IMG_4396.jpeg` | 10 | score | Courante → Sarabande boundary |
| `IMG_4397.jpeg` | 11 | score | Sarabande → Menuet I boundary |
| `IMG_4398.jpeg` | 12 | score | Menuet I → Menuet II boundary |
| `IMG_4399.jpeg` | 13 | score | Menuet II → Gigue boundary; `Menuet I D.C.` instruction |
| `IMG_4400.jpeg` | 14 | score | Gigue / end of Suite No. 1 |
| `IMG_4402.jpeg` | 104 | legend | Bass notation legend / additional definitions |

The score pages are complete and contiguous from printed page **2 through 14**.

## Movement map

Movement page ranges are inclusive because several movements begin or end partway through a page.

| Movement | Pages | Meter shown in source | Practice BPM |
|---|---:|---|---|
| Prelude | 2–5 | 4/4 | intentionally unset |
| Allemande | 5–8 | 2/2 | intentionally unset |
| Courante | 8–10 | 3/4 | intentionally unset |
| Sarabande | 10–11 | 3/4 | intentionally unset |
| Menuet I | 11–12 | 3/4 | intentionally unset |
| Menuet II | 12–13 | 3/4 | intentionally unset |
| Gigue | 13–14 | 6/8 | intentionally unset |

The printed source does not provide metronome markings in the captured pages. The project must therefore ask for or explicitly choose a practice tempo instead of inventing one and recording it as source-derived fact.

The current `PrintedNotationFixture` supports one time signature and one base BPM per fixture. Therefore this suite should be materialized as **one child practice fixture/project per movement** while retaining this source bundle as the parent provenance identity.

## Notation legend targets

The captured notation legend defines the symbol vocabulary the future recognizer/review layer should understand. The public manifest records these as parser/review targets, not as claims that every technique occurs in BWV 1007:

- hammer-on / pull-off;
- legato slide / shift slide;
- trill;
- tremolo picking;
- vibrato / shake;
- natural harmonic;
- muffled strings;
- bend / bend-and-release;
- right-hand tap / left-hand tap;
- slap / pop;
- accent / stronger accent;
- staccato;
- downstroke / upstroke;
- D.S. al Coda;
- D.C. al Fine;
- repeat measures;
- first / second endings.

## Register the private images locally

Install/update the project environment so the new CLI entry point is available, then keep the 15 image files together in one private folder.

From the repository root:

```powershell
cdlc-score-bundle describe `
  --manifest benchmarks\private_reference_sets\bwv1007_bass_dropd.yaml
```

Register the complete private set into a local Rocksmith project workspace:

```powershell
cdlc-score-bundle register C:\path\to\BWV1007_Bass_DropD `
  --manifest benchmarks\private_reference_sets\bwv1007_bass_dropd.yaml `
  --source-dir C:\path\to\private\BWV1007_Bass_DropD
```

Registration performs all of the following:

1. validates the public-safe YAML bundle definition;
2. verifies that every expected image exists;
3. verifies every image can be decoded;
4. recomputes SHA-256 for every private image;
5. fails if a capture does not match the expected image identity;
6. copies the private images into the local project under `references/printed-score/pages/`;
7. writes `references/printed-score/manifest.json` with immutable page hashes and source metadata;
8. leaves all copyrighted image bytes outside Git.

Verify the local bundle at any later time with:

```powershell
cdlc-score-bundle verify C:\path\to\BWV1007_Bass_DropD
```

Verification fails if a page is missing, undecodable, or has changed after registration.

## Why this is immediately useful

This slice does **not** pretend image recognition is finished. It makes the complete real source set usable by the project now as hash-bound, ordered, private evidence.

The registered bundle gives later stages a stable parent identity for:

```text
private page images
        ↓
ordered/hash-bound BWV1007 source bundle
        ↓
movement-specific page selection
        ↓
image normalization / deskew
        ↓
measure + notation/TAB recognition
        ↓
human review / promotion
        ↓
movement-specific PrintedNotationFixture
        ↓
deterministic tempo map
        ↓
count-in + click
        ↓
optional generated backing
        ↓
Rocksmith Bass XML / practice package
```

`movement_score_pages(...)` already returns the ordered registered private score pages for a named movement. Recognition code should consume that API rather than re-discovering page order from filenames.

## Next implementation slice

The highest-value next slice is **multi-page movement extraction**, starting with the Prelude:

1. select source pages 2–5 from the registered bundle;
2. normalize/crop the page images without changing the immutable originals;
3. segment systems and measures;
4. reconstruct TAB string/fret + notation rhythm;
5. keep region coordinates and field-level confidence;
6. emit an untrusted `PrintedNotationFixture` for the Prelude;
7. review/promote recognized events;
8. choose an explicit practice BPM;
9. use the existing `import-notation` pipeline to generate the click-aligned Rocksmith Bass XML and practice click track.

The first real end-to-end acceptance target should remain smaller than the full suite: one reviewed movement or a bounded 4–8-measure Prelude region. Once that is correct, the same source-bundle identity can scale across the remaining movements without changing provenance rules.
