"""Host memory pressure tests: no model, audio processing or network."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.host_concurrency_admission import (
    inspect_host_concurrency,
)


def _sample(sequence):
    values = iter(sequence)
    return lambda: next(values)


def test_three_stable_physical_ram_samples_admit_only_resource_window():
    pauses = []
    result = inspect_host_concurrency(
        available_probe=_sample([9.0, 8.5, 8.0]),
        sleep=pauses.append,
    )
    assert result.admitted
    assert result.sample_count == 3
    assert result.minimum_observed_available_ram_gib == 8.0
    assert pauses == [0.05, 0.05]
    assert not result.model_execution_authorized
    assert not result.network_isolation_proven
    assert not result.actual_model_ram_peak_measured


@pytest.mark.parametrize("samples", [
    [6.5, 9.0, 9.0],
    [9.0, 6.5, 9.0],
    [9.0, 8.0, 7.4],
    [9.0, 8.0, 7.49],
])
def test_unrelated_host_ram_drop_defers_even_if_previous_preflight_was_green(samples):
    result = inspect_host_concurrency(
        available_probe=_sample(samples), sleep=lambda _: None,
    )
    assert result.status == "DEFERRED"
    assert result.code == "HOST_CONCURRENCY_RAM_PRESSURE"
    assert result.minimum_observed_available_ram_gib < result.required_available_ram_gib
    assert result.sample_count <= 3


@pytest.mark.parametrize("bad", [None, True, "30.0", float("nan"), float("inf"), -1.0, "unknown"])
def test_unknown_sensor_never_becomes_permission_to_launch(bad):
    result = inspect_host_concurrency(
        available_probe=lambda: bad, sleep=lambda _: None,
    )
    assert not result.admitted
    assert result.code == "HOST_CONCURRENCY_SENSOR_UNAVAILABLE"
    assert result.sample_count == 0


def test_missing_second_sample_and_sleep_failure_fail_closed():
    calls = 0
    def intermittent():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("private user path must not be exposed")
        return 9.0
    result = inspect_host_concurrency(
        available_probe=intermittent, sleep=lambda _: None,
    )
    assert result.code == "HOST_CONCURRENCY_SENSOR_UNAVAILABLE"
    assert result.sample_count == 1
    assert "private user path" not in json.dumps(result.public_dict())

    result = inspect_host_concurrency(
        available_probe=lambda: 9.0,
        sleep=lambda _: (_ for _ in ()).throw(OSError("private filename")),
    )
    assert result.code == "HOST_CONCURRENCY_SENSOR_UNAVAILABLE"
    assert result.sample_count == 1
    assert "private filename" not in json.dumps(result.public_dict())


@pytest.mark.parametrize("params", [
    {"samples": 0}, {"samples": 1}, {"samples": 6}, {"samples": True},
    {"minimum_available_ram_gib": float("nan")},
    {"headroom_gib": -0.1}, {"headroom_gib": True},
    {"interval_seconds": -1.0}, {"interval_seconds": 10},
])
def test_invalid_bound_inputs_fail_before_any_host_probe(params):
    with pytest.raises(ValueError, match="INVALID_HOST_CONCURRENCY"):
        inspect_host_concurrency(
            available_probe=lambda: (_ for _ in ()).throw(
                AssertionError("probe should not be called")),
            sleep=lambda _: None,
            **params,
        )


def test_resource_admission_rechecked_at_actual_separator_spawn(
    tmp_path: Path, monkeypatch,
):
    from rocksmith_cdlc_generator import stems

    audio = tmp_path / "synthetic-only.wav"
    audio.write_bytes(b"test file used only for pre-spawn guard")
    cache = tmp_path / "empty-cache"
    cache.mkdir()
    output = tmp_path / "out" / "bass.wav"
    monkeypatch.setattr(stems.shutil, "which", lambda _: "/not-executed/audio-separator")

    launched = []
    def forbidden_model_launch(*args, **kwargs):
        launched.append(True)
        raise AssertionError("No process must spawn after host pressure")

    monkeypatch.setattr(stems.subprocess, "run", forbidden_model_launch)
    monkeypatch.setattr(
        stems, "inspect_host_concurrency",
        lambda: inspect_host_concurrency(
            available_probe=_sample([9.0, 8.0, 6.5]),
            sleep=lambda _: None,
        ),
    )
    adapter = stems.AudioSeparatorBassStemSeparator(
        model="synthetic.onnx", model_file_dir=cache, execution_authorized=True,
    )
    with pytest.raises(stems.StemSeparationError, match="HOST_CONCURRENCY_RAM_PRESSURE"):
        adapter.separate(audio, output)
    assert not launched
    assert not output.exists()


def test_public_report_never_contains_private_paths_or_model_claims():
    result = inspect_host_concurrency(
        available_probe=_sample([7.6, 7.7, 7.8]), sleep=lambda _: None,
    )
    report = json.dumps(result.public_dict())
    assert "source_path" not in report
    assert ".wav" not in report
    assert "process_id" not in report
    assert "STABLE_HOST_HEADROOM" in report
    assert result.model_execution_authorized is False
