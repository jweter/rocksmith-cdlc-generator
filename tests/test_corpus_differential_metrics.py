from rocksmith_cdlc_generator.corpus_differential_metrics import arrangement_presence_metrics


def test_arrangement_presence_metrics_example_1() -> None:
    assert arrangement_presence_metrics(['Bass', 'Lead', 'Rhythm']) == {'bass': True, 'lead': True, 'rhythm': True, 'symmetric': True}


def test_arrangement_presence_metrics_example_2() -> None:
    assert arrangement_presence_metrics(['bass', 'LEAD']) == {'bass': True, 'lead': True, 'rhythm': False, 'symmetric': False}


def test_arrangement_presence_metrics_example_3() -> None:
    assert arrangement_presence_metrics(['Combo', 'Vocals']) == {'bass': False, 'lead': False, 'rhythm': False, 'symmetric': False}


def test_arrangement_presence_metrics_example_4() -> None:
    assert arrangement_presence_metrics([]) == {'bass': False, 'lead': False, 'rhythm': False, 'symmetric': False}


def test_arrangement_presence_metrics_example_5() -> None:
    assert arrangement_presence_metrics(['bass', 'bass', 'bass']) == {'bass': True, 'lead': False, 'rhythm': False, 'symmetric': False}
