import pytest

from rocksmith_cdlc_generator.mobile_product_reality import render_mobile_review


def test_mobile_report_is_build_bound_responsive_and_escaped() -> None:
    html = render_mobile_review(
        {
            "commit": "abc123",
            "scenario": "synthetic timing <check>",
            "arrangements": [
                {
                    "name": "Bass",
                    "first_playable_seconds": 7.109,
                    "phase_beats": 0.0,
                    "drift_seconds": 0.0,
                }
            ],
            "desktop_acceptance_debt": ["Rocksmith 2014 playback"],
        }
    )
    assert 'name="viewport"' in html
    assert "abc123" in html
    assert "synthetic timing &lt;check&gt;" in html
    assert "Bass" in html
    assert "7.109" in html
    assert "Rocksmith 2014 playback" in html
    assert "does not verify packaging" in html


def test_mobile_report_preserves_three_first_class_arrangements() -> None:
    html = render_mobile_review(
        {
            "commit": "def456",
            "scenario": "three-arrangement parity",
            "human_result": "FLAG",
            "arrangements": [
                {"name": "Bass"},
                {"name": "Lead"},
                {"name": "Rhythm"},
            ],
        }
    )
    assert all(name in html for name in ("Bass", "Lead", "Rhythm"))
    assert "Human review: FLAG" in html


@pytest.mark.parametrize("field", ["commit", "scenario"])
def test_mobile_report_rejects_null_identity(field: str) -> None:
    report = {"commit": "abc123", "scenario": "identity-check"}
    report[field] = None

    with pytest.raises(ValueError, match=f"missing required field: {field}"):
        render_mobile_review(report)
