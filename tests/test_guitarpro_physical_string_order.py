from types import SimpleNamespace as NS

from rocksmith_cdlc_generator.guitarpro_import import _string_map


def _string(number: int, value: int):
    return NS(number=number, value=value)


def test_string_map_uses_physical_gp_string_order_not_pitch_order() -> None:
    track = NS(
        strings=[
            _string(1, 64),
            _string(2, 59),
            _string(3, 55),
            _string(4, 50),
            _string(5, 67),
            _string(6, 40),
        ]
    )

    tuning, neutral_index, open_pitch = _string_map(track)

    assert tuning == [40, 67, 50, 55, 59, 64]
    assert neutral_index == {6: 0, 5: 1, 4: 2, 3: 3, 2: 4, 1: 5}
    assert open_pitch == {6: 40, 5: 67, 4: 50, 3: 55, 2: 59, 1: 64}


def test_string_map_keeps_standard_tuning_backward_compatible() -> None:
    track = NS(
        strings=[
            _string(1, 64),
            _string(2, 59),
            _string(3, 55),
            _string(4, 50),
            _string(5, 45),
            _string(6, 40),
        ]
    )

    tuning, neutral_index, _ = _string_map(track)

    assert tuning == [40, 45, 50, 55, 59, 64]
    assert neutral_index[6] == 0
    assert neutral_index[1] == 5
