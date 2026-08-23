from rocksmith_cdlc_generator.playability_validation import chord_playability_finding, fretted_span


def test_open_strings_do_not_inflate_fretted_span() -> None:
    assert fretted_span([0, 1, 2, 3]) == 2
    assert chord_playability_finding([0, 1, 2, 3]) is None


def test_impossible_low_position_plus_ninth_fret_is_blocking() -> None:
    finding = chord_playability_finding([1, 3, 9])
    assert finding is not None
    assert finding.severity == "FAIL"
    assert finding.code == "implausible_chord_fret_span"
    assert finding.fret_span == 8
    assert "frets 1-9" in finding.message


def test_wide_but_possible_shape_requires_review_only() -> None:
    finding = chord_playability_finding([2, 7])
    assert finding is not None
    assert finding.severity == "WARNING"
    assert finding.fret_span == 5


def test_normal_barre_shape_is_not_flagged() -> None:
    assert chord_playability_finding([3, 3, 5, 5, 4, 3]) is None
