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


def test_fretboard_does_not_draw_physically_impossible_guitar_note():
    """The real GUI canvas must consume the same exact-pitch proof as its state."""
    down_tuned = [38, 43, 48, 53, 57, 62]
    note_ok = SimpleNamespace(
        start_seconds=1.0, end_seconds=1.3,
        midi=62, string_index=5, fret=0, review_required=True,
    )
    note_wrong = SimpleNamespace(
        start_seconds=1.0, end_seconds=1.3,
        midi=64, string_index=5, fret=0, review_required=True,
    )
    canvas = Mock()
    canvas.winfo_width.return_value = 400
    canvas.winfo_height.return_value = 160
    arrangement = SimpleNamespace(
        instrument="lead", tuning_midi=down_tuned, notes=[note_ok, note_wrong],
    )
    window = SimpleNamespace(
        fretboard_canvas=canvas,
        score_preview=SimpleNamespace(arrangements=[arrangement]),
        fretboard_role_var=SimpleNamespace(get=lambda: "lead"),
        _selected_time=1.1,
    )
    ArrangementPreviewSongWorkspaceWindow._draw_fretboard(window)
    # Show D4 on the physical high string; do not invent E4 by assuming E standard.
    canvas.create_oval.assert_called_once()


def test_fretboard_rejects_guitar_tuning_with_wrong_string_count():
    canvas = Mock()
    canvas.winfo_width.return_value = 400
    canvas.winfo_height.return_value = 160
    arrangement = SimpleNamespace(
        instrument="rhythm", tuning_midi=[40, 45, 50, 55, 59], notes=[],
    )
    window = SimpleNamespace(
        fretboard_canvas=canvas,
        score_preview=SimpleNamespace(arrangements=[arrangement]),
        fretboard_role_var=SimpleNamespace(get=lambda: "rhythm"),
    )
    ArrangementPreviewSongWorkspaceWindow._draw_fretboard(window)
    assert "Tuning unverified" in canvas.create_text.call_args.kwargs["text"]
    canvas.create_line.assert_not_called()
    canvas.create_oval.assert_not_called()
