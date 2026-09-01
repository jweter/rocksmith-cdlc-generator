# BWV1007 Prelude Recognition MVP

This branch begins the first real photographed-score recognition path for the private BWV1007 bass source bundle.

## Implemented in this slice

1. Re-verify the registered private score bundle before any image is processed.
2. Select a score page by its printed page number, preserving the hash-bound source identity.
3. Create a private grayscale recognition derivative without mutating the immutable registered photograph.
4. Normalize EXIF orientation, optionally downscale very large pages, and apply deterministic contrast normalization.
5. Record conservative quality diagnostics: resolution, luminance, contrast, and edge-detail warnings.
6. Persist derivative SHA-256 plus source/derivative dimensions in sidecar JSON.
7. Normalize one page or an entire movement through `cdlc-score-bundle normalize`.
8. Keep all recognition derivatives excluded from Git.

## Laptop path once this branch lands

After registering the private BWV1007 bundle, page 2 can be prepared with:

```powershell
cdlc-score-bundle normalize C:\path\to\BWV1007_Bass_DropD --page 2
```

The full Prelude source page set can be prepared with:

```powershell
cdlc-score-bundle normalize C:\path\to\BWV1007_Bass_DropD --movement prelude
```

Outputs remain private under:

```text
derived/printed-score/preprocessed/
```

## What this does not claim yet

This is the N1 preprocessing stage. It does not yet recognize notes, frets, rhythms, rests, ties, techniques, or measure boundaries. The next N2 slice will consume these normalized derivatives and detect notation/TAB systems and measures before emitting confidence-aware `PrintedNotationEvent` records.

## Acceptance boundary

The preprocessing stage is acceptable when:

- registered source page bytes remain unchanged;
- every derivative points back to the exact source SHA-256;
- derivative generation is deterministic for a fixed Pillow/runtime configuration;
- the output is a grayscale page suitable for staff/TAB recognition;
- obviously weak inputs produce quality warnings instead of silent confidence;
- private derivatives cannot be accidentally committed to the public repository.
