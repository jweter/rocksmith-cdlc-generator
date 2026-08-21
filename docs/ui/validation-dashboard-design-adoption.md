# Validation dashboard design-token adoption

This #305 slice is the first real-screen adoption of the desktop design-system foundation introduced in PR #340.

## What changed

The read-only Song Workspace validation dashboard now consumes the shared typography and spacing tokens instead of local font/spacing literals. Its dashboard state, validation state, and Rocksmith XML readiness cells are formatted through the shared semantic status registry, so each state carries explicit symbol + label text (`PASS`, `WARNING`, `FAIL`, `REVIEW REQUIRED`, or `INFO`) and is reinforced with the matching row foreground color.

The presentation mapping lives in `validation_dashboard_presentation.py` so it can be regression-tested without constructing a Tk root or requiring a display server. `validation_dashboard_ui.py` remains responsible only for widget construction and display.

## Authority boundary

This is presentation-only. It does not recalculate validation, change persisted reports, clear failures or warnings, mark XML ready, approve review findings, change source/provenance authority, or bypass packaging gates. The underlying `ValidationDashboardRow` remains the authority-bearing read model; the new presentation layer only renders that existing state.

## Accessibility and failure visibility

Color is never the sole signal. A blocked row, for example, contains `✗ FAIL` in text; validation that has not run contains `◉ REVIEW REQUIRED`; warning-bearing rows contain `⚠ WARNING`; and current ready state contains `✓ PASS`. Row foreground colors are secondary reinforcement.

This slice intentionally stops at the validation dashboard. Other Song Workspace surfaces should adopt the same tokens incrementally so each change remains small and regression-testable.
