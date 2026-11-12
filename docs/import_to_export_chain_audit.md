# Import-to-export chain audit

Slice: `rs-audit-import-to-export-chain` (roadmap: `docs/OWNER_APPROVED_ROADMAP_2026-10-25.md`, Next slices item 1).

Audited commit: `ff00e3c` (main after #751). Date: 2026-11-11.

## Scope and limits

This audit is docs-only. It records, for each stage from import to export, the module that owns it, the test or command that exercises it, and whether that evidence uses a real lawful song or only synthetic input. It claims nothing it did not run.

What was run: `PYTHONPATH=src python -m pytest` over the whole repository, and `python engineering/run_verification.py --lane golden_song_v1` with `PYTHONPATH=src`. The results are in the last section.

What was **not** possible: no private song audio, score or PSARC was available to this audit, and none is committed (by policy). Real-song sessions are recorded in `docs/product-reality/` and in local private Product Reality reports, which this audit cannot read. A stage labelled `REAL-SONG-NARRATIVE` below has a documented real-song finding but no machine-checkable real-song fixture in the repository.

Environment trap found while auditing: on this machine the installed package `rocksmith-cdlc-generator` is an editable install of a **different checkout** (`...\ExponentialEngine\workspaces\rocksmith-cdlc-generator`). Running `pytest` without `PYTHONPATH=src` imports that older copy and reports five false failures in `tests/test_rocksmith_xml.py` (count/end phrases). With `PYTHONPATH=src` those tests pass (25 passed). Anyone reproducing this audit must put the checkout's own `src` first.

## Evidence labels

- `SYNTHETIC-ONLY`: every repository-visible check uses generated or fixture inputs (for example `tests/test_three_arrangement_e2e.py` writes `b"fixture-audio"` and a hand-built tempo map).
- `REAL-SONG-NARRATIVE`: a committed document records a finding from a real-song session, but the song material is private and not reproducible from the repository.
- `EXTERNAL-TOOL`: the stage runs in a tool outside this repository (DLC Builder, the game).

## Stage table

| # | Stage | Owning modules (`src/rocksmith_cdlc_generator/`) | Exercising tests | Evidence |
|---|---|---|---|---|
| 1 | Audio intake and rights record | `audio_io.py`, `source_intake.py`, `source_rights_review.py` | `tests/test_audio_io.py` | SYNTHETIC-ONLY |
| 2 | Score / source import (MusicXML, Guitar Pro, MIDI, PSARC) | `source_import.py`, `musicxml_import.py`, `guitarpro_import.py`, `midi_import.py`, `psarc_import.py` | `tests/test_musicxml_import.py`, `tests/test_guitarpro_import.py`, `tests/test_midi_import.py`, `tests/test_psarc_import.py` | SYNTHETIC-ONLY |
| 3 | Beat and tempo map | `beats.py`, `beat_trackers.py`, `deterministic_tempo_map.py`, `tempo_pipeline.py` | `tests/test_beats.py`, `tests/test_beat_trackers.py`, `tests/test_deterministic_tempo_map.py` | SYNTHETIC-ONLY |
| 4 | Audio transcription | `transcription.py`, `transcription_pipeline.py`, `librosa_transcription.py` | `tests/test_transcription_pipeline.py` | SYNTHETIC-ONLY |
| 5 | Score-to-recording alignment and timing qualification | `alignment.py`, `alignment_onset_refinement.py`, `source_timing_qualification.py`, `shared_timeline.py` | `tests/test_alignment.py`; narrative: `docs/product-reality/source-timing-qualification-gate.md` | REAL-SONG-NARRATIVE (a real score appeared 9-10 s late; the gate was added), plus SYNTHETIC-ONLY tests |
| 6 | Reconciliation and fret mapping | `reconciliation.py`, `fret_mapping.py`, `mapping_pipeline.py`, `fretboard.py`, `chord_fingering.py` | `tests/test_reconciliation.py`, `tests/test_fret_mapping.py` | SYNTHETIC-ONLY |
| 7 | Human review authority (timing, position, technique, chords) | `reviewed_positions.py`, `reviewed_chords.py`, `reviewed_techniques.py`, `arrangement_gate.py`, `human_review_marks.py` | per-feature tests; narrative: `docs/product-reality/live-review-pass-379-382.md` | REAL-SONG-NARRATIVE (review surface used live), plus SYNTHETIC-ONLY tests |
| 8 | Validation (physical playability, structure) | `validation.py`, `guitar_validation.py`, `playability_validation.py`, `rocksmith_xml_structural_validation.py` | `tests/test_validation.py`, `tests/test_playability_validation.py`, `tests/test_rocksmith_xml_structural_validation.py` | SYNTHETIC-ONLY |
| 9 | Rocksmith XML export | `rocksmith_xml.py`, `reviewed_rocksmith_xml.py`, `reviewed_rocksmith_xml_render.py`, `authoring_export.py` | `tests/test_rocksmith_xml.py`, `tests/test_reviewed_rocksmith_xml.py`, `tests/test_authoring_export_reviewed_routing.py`, `tests/test_three_arrangement_e2e.py` | SYNTHETIC-ONLY |
| 10 | Packaging gate and build staging | `packaging_gate.py`, `package_generation.py`, `build_staging.py` | `tests/test_packaging_gate.py`, `tests/test_package_generation.py`, `tests/test_build_staging.py` | SYNTHETIC-ONLY |
| 11 | DLC Builder project handoff | `dlcbuilder.py`, `desktop_dlcbuilder_tools.py` | `tests/test_dlcbuilder.py` | SYNTHETIC-ONLY for the handoff file; the build itself is EXTERNAL-TOOL |
| 12 | Returned PSARC registration and verification | `psarc_verification.py`, `local_psarc_workspace.py`, `product_reality_psarc.py` | `tests/test_psarc_verification.py`, `tests/test_local_psarc_workspace.py`, `tests/test_product_reality_psarc.py` | SYNTHETIC-ONLY |
| 13 | Private real-song Product Reality (XML validation) | `private_product_reality.py`, `product_reality_xml_validation.py` | `tests/test_private_product_reality_xml_validation_integration.py` (semantics on synthetic fixtures) | Runs on real private songs only locally; the repository sees synthetic fixtures |
| 14 | Manual installation and in-game loading/playback | none (not automated) | none | EXTERNAL-TOOL / human-only (`docs/UNATTENDED_VERIFICATION.md` category 4 until automation exists) |

## Repository-visible facts that bound the claims

- `engineering/product-reality-attestations.json` has `"lanes": {}`: no real-song Product Reality lane is machine-attested in the repository.
- The only executable verification lane, `golden_song_v1`, declares its own evidence as "Repository-safe synthetic notation, arrangement/timeline, technique import, and Rocksmith XML export regression" and its golden scenario states that packaged/gameplay and musical judgment remain separate Product Reality evidence.
- `tests/test_three_arrangement_e2e.py` drives import-to-export through `export_project_bass_authoring`, `export_project_guitar_authoring`, `stage_build` and `prepare_dlcbuilder_project`, but on a fixture project (`b"fixture-audio"`, a four-beat hand-written tempo map).

## Highest-priority unverified real-song seam

No stage was found broken: the whole suite passes on main when the checkout's own `src` is used (see results). No seam is established as broken.

**No stage from 1 to 14 is proven on a real song by anything the repository can show.** Stages 1-10 are exercised end to end only on synthetic inputs, plus narrative real-song findings for alignment (5) and review (7), where a real-song problem was found and fixed. This audit therefore does not call any stage proven for real songs.

The **highest-priority unverified seam** is the end of the chain, **stages 11-14: DLC Builder build, returned PSARC verification, installation and in-game load of a real export**. It is chosen by product value, not by position: the milestone is a *game-compatible artifact* from a real song, and nothing in the repository can show that a real export passed DLC Builder or PSARC verification, or loaded in the game. The attestation file is empty and the in-game step is human-only today. Item 2 of the roadmap's Next slices should therefore start from a locally run real-song export through stages 9-12 on the private corpus allowed by `PROJECT_PLAN.md` rule 26, not from another synthetic test, and should record "nothing broken" if that run is clean.

## Recommended next evidence (not done here)

1. Run the private Product Reality runner on one lawful development song through stages 9-12 and record a sanitized aggregate result (PASS/FAIL per stage, tool versions, content hashes only) in a new attestation lane.
2. If stage 11 or 12 fails on the real export, that is the seam for `rs-repair-first-broken-seam`; if both pass, in-game load (stage 14) is the seam and stays human-only until a launcher-safe smoke exists.
3. Make the editable-install trap above fail loudly (for example a test asserting `rocksmith_cdlc_generator.__file__` is under the checkout) so a stale install cannot report false failures.

## Results of the runs

- `PYTHONPATH=src python -m pytest -q`: **2221 passed, 3 skipped** (commit `ff00e3c`).
- `python engineering/run_verification.py --lane golden_song_v1` **without** `PYTHONPATH=src`: FAILED, 5 failures in `tests/test_rocksmith_xml.py`, caused by the stale editable install described above, not by the checkout.
- `PYTHONPATH=src python -m pytest tests/test_rocksmith_xml.py -q`: 25 passed.
- CI (`golden-song-v1`, Windows jobs) passed on #751 at this commit, which is consistent with the checkout being healthy.
