"""Missing instrument tuning must not be silently represented as standard tuning."""
from types import SimpleNamespace
from unittest.mock import Mock

from rocksmith_cdlc_generator.arrangement_preview_ui import ArrangementPreviewSongWorkspaceWindow


def test_fretboard_missing_tuning_is_explicit_and_draws_no_strings():
    canvas = Mock()
    canvas.winfo_width.return_value = 400
    canvas.winfo_height.return_value = 160
    arrangement = SimpleNamespace(instrument="bass", tuning_midi=None, notes=[])
    window = SimpleNamespace(
        fretboard_canvas=canvas,
        score_preview=SimpleNamespace(arrangements=[arrangement]),
        fretboard_role_var=SimpleNamespace(get=lambda: "bass"),
    )

    ArrangementPreviewSongWorkspaceWindow._draw_fretboard(window)

    canvas.create_text.assert_called_once()
    assert "Tuning unverified" in canvas.create_text.call_args.kwargs["text"]
    canvas.create_line.assert_not_called()
    canvas.create_oval.assert_not_called()