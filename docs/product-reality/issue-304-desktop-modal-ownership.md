# Desktop modal ownership fix (#304 / #305)

## Product symptom

Several error, warning, and informational message boxes in the base Windows
desktop shell did not declare an owner. Tk/Windows may place an unowned modal
behind the application or on another monitor. The main window then remains
blocked while the required recovery message is not visible, which looks like
a frozen application.

Affected paths included:

- background-operation failures;
- project-open failures;
- project-required notices;
- Bass/Lead/Rhythm mapping-selection warnings and confirmation errors;
- rights/provenance selection and recording errors.

## Resolution

Every `DesktopApp` message box now provides an explicit `parent`. Messages
raised from the New Project child window remain owned by that child dialog;
all other messages are owned by the main application window.

The change is presentation/recoverability only. It does not alter arrangement
authority, provenance, validation, export, or packaging behavior.

## Regression protection

`tests/test_desktop_modal_ownership.py` parses the real `DesktopApp` class
and fails if any future message-box call omits an explicit owner or introduces
an unexpected parent.
