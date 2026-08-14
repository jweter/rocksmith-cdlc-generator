# One-command first draft

`cdlc-draft` is the shortest safe path from local files to the existing automatic Bass first-draft workflow.

## Goal

A normal user should not need to understand the internal pipeline before starting. Given a local recording, and optionally a local tab/notation/chart source, the command:

1. creates the project from immutable recording audio;
2. records the audio intake receipt and rights/provenance classification;
3. imports the optional Bass symbolic source through the existing MIDI, Guitar Pro 3/4/5, MusicXML/MXL, or selected PSARC adapter;
4. records that source independently with its own rights/provenance classification;
5. hands the project to `cdlc-auto` so deterministic normalization, timing, transcription, alignment, reconciliation, mapping, and validation can advance until the first real human gate.

The command does not select ambiguous tab tracks, approve unknown rights, accept source/audio disagreements, or approve low-confidence musical output.

## Examples

Start from audio only. The title defaults to the filename stem:

```powershell
cdlc-draft "C:\Music\My Song.flac" --artist "Artist"
```

Start from user-owned local audio plus a local Guitar Pro Bass source:

```powershell
cdlc-draft "C:\Music\My Song.flac" `
  --artist "Artist" `
  --title "My Song" `
  --rights-class user_owned_local `
  --notation "C:\Tabs\My Song.gp5" `
  --notation-rights-class user_owned_local
```

If the notation contains multiple plausible Bass tracks, supply the track explicitly after reviewing the file:

```powershell
cdlc-draft "C:\Music\My Song.flac" `
  --rights-class user_owned_local `
  --notation "C:\Tabs\My Song.gp5" `
  --notation-rights-class user_owned_local `
  --track-index 2
```

## Human gates

`unknown` is the default rights class for both recording audio and notation. With that default, the project is created and provenance is retained, but automatic progression stops at the source-rights gate.

Audio and notation have separate rights flags intentionally. Having a lawful local recording does not imply a separate commercial tab file has the same use rights.

Ambiguous notation import returns a structured error that includes the already-created `project_path`. The project is preserved so the user or future GUI can inspect the source and resume with an explicit track/part choice instead of redoing ingest.

## GUI direction

The eventual Windows Song Workspace can call the same bootstrap function directly rather than shelling out. Its structured result already contains the project path, source receipts, automatic stages executed, stop reason, next workflow step, and full final plan. That lets the GUI present one clear action such as **Review source rights**, **Choose Bass track**, or **Review generated draft** instead of exposing internal command sequencing.

## Safety boundaries

- local files only; no Spotify, Apple Music, YouTube, or paid-tab ripping;
- no rights class is inferred automatically;
- no ambiguous source/track choice is made automatically;
- no uncertain musical output is silently promoted to reviewed truth;
- no live Rocksmith installation, player profile, official DLC, or NoCableLauncher modification;
- generated/private project artifacts remain under the existing gitignored workspace.
