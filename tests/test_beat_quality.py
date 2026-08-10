from rocksmith_cdlc_generator.beat_quality import review_tempo_map
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap


def _map(times: list[float], confidences: list[float] | None = None) -> TempoMap:
    confidences = confidences or [0.9] * len(times)
    return TempoMap(
        engine="test",
        beats=[
            BeatEvent(
                time=time,
                beat=(index % 4) + 1,
                measure=(index // 4) + 1,
                bpm=120.0,
                confidence=confidences[index],
                is_downbeat=index % 4 == 0,
            )
            for index, time in enumerate(times)
        ],
    )


def test_regular_grid_passes_review() -> None:
    review = review_tempo_map(_map([0.0, 0.5, 1.0, 1.5, 2.0, 2.5]))
    assert review.status == "PASS"
    assert review.interval_cv == 0.0


def test_irregular_grid_requires_review() -> None:
    review = review_tempo_map(_map([0.0, 0.5, 1.0, 1.9, 2.4, 2.9]))
    assert review.status == "WARNING"
    assert review.largest_interval_deviation_ms is not None
    assert review.largest_interval_deviation_ms > 150.0


def test_too_few_beats_fails() -> None:
    review = review_tempo_map(_map([0.0]))
    assert review.status == "FAIL"
