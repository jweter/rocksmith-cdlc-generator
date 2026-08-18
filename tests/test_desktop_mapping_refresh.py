from __future__ import annotations

from rocksmith_cdlc_generator.desktop_app import _bare_mapping_label, _mapping_refresh_value


LABELS = [
    "0: Bass — bass — 412 notes",
    "1: James Hetfield — guitar — 1532 notes",
    "2: Kirk Hammett — guitar — 1104 notes",
]


def test_refresh_preserves_valid_pending_selection_without_persisted_mapping() -> None:
    assert _mapping_refresh_value(
        current_value=LABELS[2],
        labels=LABELS,
        mapped_track_index=None,
    ) == LABELS[2]


def test_refresh_drops_pending_selection_that_no_longer_exists() -> None:
    assert _mapping_refresh_value(
        current_value="9: Removed Track — guitar — 20 notes",
        labels=LABELS,
        mapped_track_index=None,
    ) == ""


def test_persisted_mapping_remains_authoritative_over_pending_selection() -> None:
    assert _mapping_refresh_value(
        current_value=LABELS[2],
        labels=LABELS,
        mapped_track_index=1,
        human_confirmed=True,
    ) == LABELS[1] + " ✓ confirmed"


def test_unconfirmed_persisted_mapping_keeps_review_marker() -> None:
    assert _mapping_refresh_value(
        current_value=LABELS[2],
        labels=LABELS,
        mapped_track_index=1,
        human_confirmed=False,
    ) == LABELS[1] + " • review required"


def test_bare_mapping_label_strips_only_known_status_suffix() -> None:
    assert _bare_mapping_label(LABELS[1] + " ✓ confirmed") == LABELS[1]
    assert _bare_mapping_label(LABELS[1] + " • review required") == LABELS[1]
    assert _bare_mapping_label(LABELS[1]) == LABELS[1]
