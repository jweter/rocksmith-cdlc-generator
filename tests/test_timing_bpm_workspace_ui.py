from __future__ import annotations

from rocksmith_cdlc_generator.timing_bpm_workspace_ui import (
    TimingBpmWorkspaceMixin,
    local_bpm_for_beat,
)


def test_local_bpm_uses_interval_after_selected_beat() -> None:
    assert local_bpm_for_beat([0.0, 0.5, 1.5], 0) == 120.0
    assert local_bpm_for_beat([0.0, 0.5, 1.5], 1) == 60.0


def test_local_bpm_last_beat_uses_previous_interval() -> None:
    assert local_bpm_for_beat([0.0, 0.5, 1.5], 2) == 60.0


def test_local_bpm_fails_closed_for_unusable_grid() -> None:
    assert local_bpm_for_beat([], 0) is None
    assert local_bpm_for_beat([0.0], 0) is None
    assert local_bpm_for_beat([0.0, 0.0], 0) is None
    assert local_bpm_for_beat([0.0, 0.5], -1) is None
    assert local_bpm_for_beat([0.0, 0.5], 2) is None


def test_final_workspace_includes_local_bpm_mixin() -> None:
    from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow

    assert issubclass(AudioOutputSongWorkspaceWindow, TimingBpmWorkspaceMixin)
