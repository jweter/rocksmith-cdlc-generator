from pathlib import Path

SOURCE = Path(__file__).parents[1] / "src" / "rocksmith_cdlc_generator" / "live_review_enhancements.py"


def test_audio_transport_is_not_parented_to_draft_gated_frame() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "transport = ttk.Frame(self.live_review_content_frame)" not in source


def test_audio_transport_stays_above_preview_canvases() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'transport.pack(fill="x", pady=(0, 6), before=self.eof_tab_canvas)' in source


def test_note_navigation_remains_inside_draft_gated_content() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "navigation = ttk.Frame(self.live_review_content_frame)" in source
    assert 'ttk.Button(transport, text="First note"' not in source
    assert 'ttk.Button(transport, text="Next note"' not in source
