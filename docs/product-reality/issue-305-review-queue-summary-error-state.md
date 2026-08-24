# Review Queue summary unavailable state

## Product Reality finding

The Song Workspace Review Queue summary caught summary-building failures but rendered the raw exception message directly in the authoring UI. A filesystem or parsing exception could therefore expose private local paths or score filenames, while the message did not explain whether review authority changed or how to recover.

## Correction

The failure presentation is now deterministic and sanitized:

- it uses a non-color-only warning symbol and explicit **REVIEW SUMMARY UNAVAILABLE** label;
- it states that review-required events remain unchanged;
- it tells the user to refresh the workspace to retry;
- it retains only the exception class as bounded diagnostics;
- it never renders the exception message itself.

Focused regression coverage supplies an exception containing a private Windows path and verifies that neither the directory nor score filename reaches the presentation text.

## Safety boundary

This is presentation-only. It does not suppress, accept, regroup, reclassify, or mutate review items. It does not alter source, mapping, timing, arrangement, validation, export, or packaging authority. The state fails closed by making the summary explicitly unavailable while preserving the underlying review requirements.
