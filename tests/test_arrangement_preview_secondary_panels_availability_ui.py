"""Regression coverage for issue #563.

The "Human-reviewed event timing", "Human-reviewed techniques",
"Human-reviewed chord fingering", "Human-reviewed source track trust", and
live-review transport/selected-note-review panels in the Arrangement Preview
tab each rendered full-height entry fields/buttons (always-disabled without an
arrangement draft) even on a score-only project with no registered complete
score. This mirrors the fretboard/position-review fix in
``test_arrangement_preview_availability_ui.py`` and the composition fix in
``test_score_role_composition_workspace_ui.py``: collapse each panel's
interactive controls into a compact status line when an arrangement draft is
unavailable, and restore them once it exists.
"""

from __future__ import annotations

from rocksmith_cdlc_generator.arrangement_event_timing_ui import (
    ArrangementEventTimingSongWorkspaceWindow,
)
from rocksmith_cdlc_generator.arrangement_technique_ui import (
    ArrangementTechniqueSongWorkspaceWindow,
)
from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow
from rocksmith_cdlc_generator.chord_fingering_ui import ChordFingeringSongWorkspaceWindow
from rocksmith_cdlc_generator.live_review_enhancements import LiveReviewEnhancementMixin
from rocksmith_cdlc_generator.track_trust_workspace_ui import TrackTrustWorkspaceMixin


class _Packable:
    """Records pack()/pack_forget() calls, mirroring a real ttk widget's visibility state."""

    def __init__(self) -> None:
        self.packed = False

    def pack(self, **_kwargs) -> None:
        self.packed = True

    def pack_forget(self) -> None:
        self.packed = False


class _Base:
    def refresh(self) -> None:
        pass


def test_final_song_workspace_includes_all_three_secondary_panel_mixins() -> None:
    assert ArrangementEventTimingSongWorkspaceWindow in AudioOutputSongWorkspaceWindow.__mro__
    assert ArrangementTechniqueSongWorkspaceWindow in AudioOutputSongWorkspaceWindow.__mro__
    assert ChordFingeringSongWorkspaceWindow in AudioOutputSongWorkspaceWindow.__mro__
    assert TrackTrustWorkspaceMixin in AudioOutputSongWorkspaceWindow.__mro__
    assert LiveReviewEnhancementMixin in AudioOutputSongWorkspaceWindow.__mro__


class _EventTimingHarness(ArrangementEventTimingSongWorkspaceWindow, _Base):
    def __init__(self) -> None:
        self.score_preview = None
        self.event_timing_content_frame = _Packable()
        self.event_timing_unavailable_label = _Packable()


def test_event_timing_controls_start_collapsed_with_no_arrangement_draft() -> None:
    window = _EventTimingHarness()
    window._update_event_timing_availability()

    assert window.event_timing_content_frame.packed is False
    assert window.event_timing_unavailable_label.packed is True


def test_event_timing_controls_expand_once_an_arrangement_draft_is_available() -> None:
    window = _EventTimingHarness()
    window.score_preview = object()
    window._update_event_timing_availability()

    assert window.event_timing_content_frame.packed is True
    assert window.event_timing_unavailable_label.packed is False


def test_event_timing_controls_recollapse_when_the_arrangement_draft_disappears_again() -> None:
    window = _EventTimingHarness()
    window.score_preview = object()
    window._update_event_timing_availability()

    window.score_preview = None
    window._update_event_timing_availability()

    assert window.event_timing_content_frame.packed is False
    assert window.event_timing_unavailable_label.packed is True


class _TechniqueHarness(ArrangementTechniqueSongWorkspaceWindow, _Base):
    def __init__(self) -> None:
        self.score_preview = None
        self.technique_content_frame = _Packable()
        self.technique_unavailable_label = _Packable()


def test_technique_controls_start_collapsed_with_no_arrangement_draft() -> None:
    window = _TechniqueHarness()
    window._update_technique_availability()

    assert window.technique_content_frame.packed is False
    assert window.technique_unavailable_label.packed is True


def test_technique_controls_expand_once_an_arrangement_draft_is_available() -> None:
    window = _TechniqueHarness()
    window.score_preview = object()
    window._update_technique_availability()

    assert window.technique_content_frame.packed is True
    assert window.technique_unavailable_label.packed is False


def test_technique_controls_recollapse_when_the_arrangement_draft_disappears_again() -> None:
    window = _TechniqueHarness()
    window.score_preview = object()
    window._update_technique_availability()

    window.score_preview = None
    window._update_technique_availability()

    assert window.technique_content_frame.packed is False
    assert window.technique_unavailable_label.packed is True


class _ChordFingeringHarness(ChordFingeringSongWorkspaceWindow, _Base):
    def __init__(self) -> None:
        self.score_preview = None
        self.chord_fingering_content_frame = _Packable()
        self.chord_fingering_unavailable_label = _Packable()


def test_chord_fingering_controls_start_collapsed_with_no_arrangement_draft() -> None:
    window = _ChordFingeringHarness()
    window._update_chord_fingering_availability()

    assert window.chord_fingering_content_frame.packed is False
    assert window.chord_fingering_unavailable_label.packed is True


def test_chord_fingering_controls_expand_once_an_arrangement_draft_is_available() -> None:
    window = _ChordFingeringHarness()
    window.score_preview = object()
    window._update_chord_fingering_availability()

    assert window.chord_fingering_content_frame.packed is True
    assert window.chord_fingering_unavailable_label.packed is False


def test_chord_fingering_controls_recollapse_when_the_arrangement_draft_disappears_again() -> None:
    window = _ChordFingeringHarness()
    window.score_preview = object()
    window._update_chord_fingering_availability()

    window.score_preview = None
    window._update_chord_fingering_availability()

    assert window.chord_fingering_content_frame.packed is False
    assert window.chord_fingering_unavailable_label.packed is True


class _TrackTrustHarness(TrackTrustWorkspaceMixin, _Base):
    def __init__(self) -> None:
        self.score_preview = None
        self.track_trust_content_frame = _Packable()
        self.track_trust_unavailable_label = _Packable()


def test_track_trust_controls_start_collapsed_with_no_arrangement_draft() -> None:
    window = _TrackTrustHarness()
    window._update_track_trust_availability()

    assert window.track_trust_content_frame.packed is False
    assert window.track_trust_unavailable_label.packed is True


def test_track_trust_controls_expand_once_an_arrangement_draft_is_available() -> None:
    window = _TrackTrustHarness()
    window.score_preview = object()
    window._update_track_trust_availability()

    assert window.track_trust_content_frame.packed is True
    assert window.track_trust_unavailable_label.packed is False


def test_track_trust_controls_recollapse_when_the_arrangement_draft_disappears_again() -> None:
    window = _TrackTrustHarness()
    window.score_preview = object()
    window._update_track_trust_availability()

    window.score_preview = None
    window._update_track_trust_availability()

    assert window.track_trust_content_frame.packed is False
    assert window.track_trust_unavailable_label.packed is True


class _LiveReviewHarness(LiveReviewEnhancementMixin, _Base):
    """Duck-typed host: ``_active_measure_arrangement`` is normally supplied by
    ``EOFMeasureReviewMixin``, stubbed directly here the same way
    ``tests/test_live_review_enhancements.py``'s ``_FakeMixinHost`` does, so this
    test does not need the rest of that mixin's Tk-building machinery."""

    def __init__(self) -> None:
        self._arrangement = None
        self.eof_tab_canvas = object()
        self.live_review_content_frame = _Packable()
        self.live_review_unavailable_label = _Packable()

    def _active_measure_arrangement(self):
        return self._arrangement


def test_live_review_controls_start_collapsed_with_no_arrangement_draft() -> None:
    window = _LiveReviewHarness()
    window._update_live_review_availability()

    assert window.live_review_content_frame.packed is False
    assert window.live_review_unavailable_label.packed is True


def test_live_review_controls_expand_once_an_arrangement_draft_is_available() -> None:
    window = _LiveReviewHarness()
    window._arrangement = object()
    window._update_live_review_availability()

    assert window.live_review_content_frame.packed is True
    assert window.live_review_unavailable_label.packed is False


def test_live_review_controls_recollapse_when_the_arrangement_draft_disappears_again() -> None:
    window = _LiveReviewHarness()
    window._arrangement = object()
    window._update_live_review_availability()

    window._arrangement = None
    window._update_live_review_availability()

    assert window.live_review_content_frame.packed is False
    assert window.live_review_unavailable_label.packed is True
