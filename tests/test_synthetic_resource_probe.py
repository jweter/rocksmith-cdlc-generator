"""Bounded synthetic-only RAM probe regression tests. Never run a model."""
from __future__ import annotations

import json
import sys

import pytest

from rocksmith_cdlc_generator.synthetic_resource_probe import (
    SyntheticResourceProbeResult, run_synthetic_resource_probe,
)


def test_synthetic_probe_measures_child_rss_without_launching_model():
    if not (sys.platform == "win32" or sys.platform.startswith("linux")):
        pytest.skip("Process RSS probe supports Windows and Linux only")
    result = run_synthetic_resource_probe(
        allocation_mib=8, hold_ms=400, process_limit_mib=128,
        available_probe=lambda: 12.0,
    )
    assert result.status == "SYNTHETIC_ONLY_PASS"
    assert result.sample_count >= 2
    assert result.peak_process_rss_mib is not None
    assert result.peak_process_rss_mib >= 4.0
    assert result.elapsed_seconds < 6.0
    assert result.exit_code == 0
    assert not result.network_isolation_proven
    assert not result.model_execution_proven
    assert not result.separator_quality_proven
    assert not result.application_ready


def test_readiness_blocks_low_available_physical_ram_without_subprocess(monkeypatch):
    import rocksmith_cdlc_generator.synthetic_resource_probe as module

    def forbidden(*a, **kw):
        raise AssertionError("No child may spawn below RAM floor")

    monkeypatch.setattr(module.subprocess, "Popen", forbidden)
    result = run_synthetic_resource_probe(available_probe=lambda: .1)
    assert result.status == "BLOCKED_PHYSICAL_RAM"
    assert result.sample_count == 0
    assert result.exit_code is None


def test_bad_sensor_blocks_before_subprocess(monkeypatch):
    import rocksmith_cdlc_generator.synthetic_resource_probe as module

    def forbidden(*a, **kw):
        raise AssertionError("Cannot start when RAM cannot be measured")

    monkeypatch.setattr(module.subprocess, "Popen", forbidden)
    result = run_synthetic_resource_probe(available_probe=lambda: float("nan"))
    assert result.status == "BLOCKED_PHYSICAL_RAM"
    assert result.minimum_observed_available_ram_gib is None


def test_peak_rss_threshold_terminates_synthetic_child():
    result = run_synthetic_resource_probe(
        allocation_mib=8, hold_ms=1500, process_limit_mib=16,
        available_probe=lambda: 12.0,
        resident_sampler=lambda pid, proc: 200 * 1024 * 1024,
    )
    assert result.status == "PROCESS_RSS_LIMIT"
    assert result.peak_process_rss_mib == 200
    assert result.sample_count >= 1
    assert result.elapsed_seconds < 5.0


def test_runtime_host_ram_drop_terminates_synthetic_child():
    counter = 0

    def changing_memory():
        nonlocal counter
        counter += 1
        return 12.0 if counter < 4 else .01

    result = run_synthetic_resource_probe(
        allocation_mib=8, hold_ms=1500, available_probe=changing_memory,
        resident_sampler=lambda pid, proc: 18 * 1024 * 1024,
    )
    assert result.status == "HOST_PHYSICAL_RAM_FLOOR"
    assert result.minimum_observed_available_ram_gib < .5


@pytest.mark.parametrize("kwargs", [
    {"allocation_mib": 0},
    {"allocation_mib": 1000},
    {"allocation_mib": True},
    {"hold_ms": 15000},
    {"hold_ms": 0},
    {"process_limit_mib": 2},
    {"process_limit_mib": 1000},
    {"minimum_available_ram_gib": -1},
])
def test_invalid_bounds_never_launch(kwargs):
    with pytest.raises(ValueError):
        run_synthetic_resource_probe(**kwargs)


def test_public_report_has_no_paths_or_private_source_events():
    result = run_synthetic_resource_probe(
        allocation_mib=1, hold_ms=350, available_probe=lambda: 12.0,
    )
    value = result.public_dict()
    dump = json.dumps(value)
    assert set(value) >= {
        "status", "peak_process_rss_mib", "elapsed_seconds",
        "sample_count", "minimum_observed_available_ram_gib",
        "model_execution_proven", "network_isolation_proven",
    }
    assert "source_path" not in dump
    assert "input_audio" not in dump
    assert "model_filename" not in dump
    assert value["model_execution_proven"] is False
    assert value["network_isolation_proven"] is False


def test_cli_default_is_readiness_only_and_never_spawns(monkeypatch, capsys):
    import rocksmith_cdlc_generator.synthetic_resource_probe_cli as cli
    import rocksmith_cdlc_generator.synthetic_resource_probe as module

    monkeypatch.setattr(cli, "available_memory_gib", lambda: 6.25)
    monkeypatch.setattr(sys, "argv", ["cdlc-synthetic-ram-probe"])
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("No worker is allowed in readiness mode")
    ))
    cli.main()
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "READINESS_ONLY"
    assert report["available_physical_ram_gib"] == 6.25
    assert report["network_isolation_proven"] is False


def test_cli_opt_in_requires_exact_switch(monkeypatch):
    from rocksmith_cdlc_generator.synthetic_resource_probe_cli import build_parser

    parsed = build_parser().parse_args([])
    assert not parsed.run_synthetic
    explicit = build_parser().parse_args(["--run-synthetic", "--allocation-mib", "4"])
    assert explicit.run_synthetic
    assert explicit.allocation_mib == 4


def test_live_rss_monitor_disappearing_never_reports_pass():
    readings = 0

    def two_then_missing(pid, process):
        nonlocal readings
        readings += 1
        return 12 * 1024 * 1024 if readings <= 2 else None

    result = run_synthetic_resource_probe(
        allocation_mib=8, hold_ms=800,
        available_probe=lambda: 12.0,
        resident_sampler=two_then_missing,
    )
    assert readings >= 3
    assert result.status == "RESOURCE_SAMPLE_FAILED"
    assert result.sample_count == 2
    assert result.exit_code is not None
    assert result.status != "SYNTHETIC_ONLY_PASS"


def test_rss_sampler_exception_is_blocking_not_unhandled():
    readings = 0

    def flaky(pid, process):
        nonlocal readings
        readings += 1
        if readings >= 2:
            raise OSError("source path private error!")
        return 12 * 1024 * 1024

    result = run_synthetic_resource_probe(
        allocation_mib=8, hold_ms=800,
        available_probe=lambda: 12.0,
        resident_sampler=flaky,
    )
    assert result.status == "RESOURCE_SAMPLE_FAILED"
    assert "source path" not in json.dumps(result.public_dict())
