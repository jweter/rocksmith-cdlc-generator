from pathlib import Path

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.beats import (
    BeatEvent,
    TempoMap,
    read_tempo_map,
    write_beats_csv,
    write_tempo_map,
)


def sample_tempo_map() -> TempoMap:
    return TempoMap(
        engine="synthetic-test",
        engine_version="1",
        beats=[
            BeatEvent(
                time=0.5,
                beat=1,
                measure=1,
                bpm=120.0,
                confidence=0.99,
                is_downbeat=True,
            ),
            BeatEvent(
                time=1.0,
                beat=2,
                measure=1,
                bpm=120.0,
                confidence=0.98,
            ),
            BeatEvent(
                time=1.5,
                beat=3,
                measure=1,
                bpm=119.8,
                confidence=0.97,
            ),
        ],
    )


def test_tempo_map_requires_strictly_increasing_times() -> None:
    with pytest.raises(ValidationError):
        TempoMap(
            engine="bad-test",
            beats=[
                BeatEvent(time=1.0, beat=1, measure=1, bpm=120, confidence=1),
                BeatEvent(time=1.0, beat=2, measure=1, bpm=120, confidence=1),
            ],
        )


def test_median_bpm() -> None:
    assert sample_tempo_map().median_bpm == 120.0


def test_tempo_map_round_trip(tmp_path: Path) -> None:
    output = tmp_path / "tempo_map.json"
    write_tempo_map(sample_tempo_map(), output)
    loaded = read_tempo_map(output)
    assert loaded.engine == "synthetic-test"
    assert len(loaded.beats) == 3


def test_beats_csv_export(tmp_path: Path) -> None:
    output = tmp_path / "beats.csv"
    write_beats_csv(sample_tempo_map(), output)
    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "time,beat,measure,bpm,confidence,is_downbeat"
    assert lines[1].endswith(",true")
