from pathlib import Path

SOURCE = Path(__file__).parents[1] / "src" / "rocksmith_cdlc_generator" / "live_review_enhancements.py"


def test_audio_transport_is_not_parented_to_draft_gated_frame() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "transport = ttk.Frame(self.live_review_content_frame)" not in source
