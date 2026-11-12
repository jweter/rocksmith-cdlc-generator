from rocksmith_cdlc_generator.corpus_metric_arrangement_presence import arrangement_presence


def test_all_three_present_is_symmetric() -> None:
    assert arrangement_presence(["Bass", "Lead", "Rhythm"]) == {
        "bass": True,
        "lead": True,
        "rhythm": True,
        "symmetric": True,
    }


def test_case_insensitive_and_missing_rhythm_is_not_symmetric() -> None:
    assert arrangement_presence(["bass", "LEAD"]) == {
        "bass": True,
        "lead": True,
        "rhythm": False,
        "symmetric": False,
    }


def test_unrelated_names_are_none_of_the_three() -> None:
    assert arrangement_presence(["Combo", "Vocals"]) == {
        "bass": False,
        "lead": False,
        "rhythm": False,
        "symmetric": False,
    }


def test_empty_list_means_none_present() -> None:
    assert arrangement_presence([]) == {
        "bass": False,
        "lead": False,
        "rhythm": False,
        "symmetric": False,
    }
