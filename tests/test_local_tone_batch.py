from pathlib import Path

import pytest

import rocksmith_cdlc_generator.local_tone_batch as batch
from rocksmith_cdlc_generator.tone_reference_library import (
    ToneReferenceLibrary,
    merge_scan_results,
    read_library,
    write_library,
)


def _roots(tmp_path: Path):
    rocksmith = tmp_path / "Rocksmith2014"
    dlc = rocksmith / "dlc"
    dlc.mkdir(parents=True)
    workspace = tmp_path / "private"
    library = workspace / "tone-library.json"
    return rocksmith, dlc, workspace, library


def test_source_map_is_exact_and_defaults_unknown(tmp_path: Path) -> None:
    _, dlc, _, _ = _roots(tmp_path)
    first = dlc / "first_p.psarc"
    second = dlc / "second_p.psarc"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    resolver = batch.source_resolver_from_map(dlc, {"first_p.psarc": "official_rocksmith"})
    assert resolver(first) == "official_rocksmith"
    assert resolver(second) == "unknown"


def test_source_map_rejects_path_escape(tmp_path: Path) -> None:
    _, dlc, _, _ = _roots(tmp_path)
    with pytest.raises(ValueError, match="escaped"):
        batch.source_resolver_from_map(dlc, {"../outside.psarc": "official_rocksmith"})


def test_batch_isolates_failure_and_persists_success(monkeypatch, tmp_path: Path) -> None:
    rocksmith, dlc, workspace, library_path = _roots(tmp_path)
    good = dlc / "a_good_p.psarc"
    bad = dlc / "b_bad_p.psarc"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")

    def fake_index(source: Path, **kwargs) -> ToneReferenceLibrary:
        if source.name.startswith("b_bad"):
            raise RuntimeError("synthetic extraction failure")
        existing = read_library(kwargs["library_path"]) if kwargs["library_path"].is_file() else None
        updated = merge_scan_results(
            kwargs["dlc_root"],
            [(source, kwargs["source_type"], [])],
            existing=existing,
        )
        write_library(updated, kwargs["library_path"])
        return updated

    monkeypatch.setattr(batch, "index_local_psarc", fake_index)
    report = batch.scan_changed_psarcs(
        dlc_root=dlc,
        rocksmith_root=rocksmith,
        workspace_root=workspace,
        library_path=library_path,
        source_resolver=lambda _: "unknown",
    )

    assert report.planned_count == 2
    assert report.succeeded_count == 1
    assert report.failed_count == 1
    assert read_library(library_path).psarcs[0].path == str(good.resolve())


def test_failed_package_is_retried_while_success_is_resumed(monkeypatch, tmp_path: Path) -> None:
    rocksmith, dlc, workspace, library_path = _roots(tmp_path)
    good = dlc / "a_good_p.psarc"
    bad = dlc / "b_bad_p.psarc"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")
    attempts: list[str] = []

    def fake_index(source: Path, **kwargs) -> ToneReferenceLibrary:
        attempts.append(source.name)
        if source.name.startswith("b_bad"):
            raise RuntimeError("still bad")
        existing = read_library(kwargs["library_path"]) if kwargs["library_path"].is_file() else None
        updated = merge_scan_results(kwargs["dlc_root"], [(source, kwargs["source_type"], [])], existing=existing)
        write_library(updated, kwargs["library_path"])
        return updated

    monkeypatch.setattr(batch, "index_local_psarc", fake_index)
    kwargs = dict(
        dlc_root=dlc,
        rocksmith_root=rocksmith,
        workspace_root=workspace,
        library_path=library_path,
        source_resolver=lambda _: "unknown",
    )
    batch.scan_changed_psarcs(**kwargs)
    attempts.clear()
    second = batch.scan_changed_psarcs(**kwargs)

    assert attempts == ["b_bad_p.psarc"]
    assert second.planned_count == 1
    assert second.failed_count == 1


def test_limit_caps_one_run_without_marking_unprocessed_complete(monkeypatch, tmp_path: Path) -> None:
    rocksmith, dlc, workspace, library_path = _roots(tmp_path)
    for name in ("a.psarc", "b.psarc", "c.psarc"):
        (dlc / name).write_bytes(name.encode())

    def fake_index(source: Path, **kwargs) -> ToneReferenceLibrary:
        existing = read_library(kwargs["library_path"]) if kwargs["library_path"].is_file() else None
        updated = merge_scan_results(kwargs["dlc_root"], [(source, kwargs["source_type"], [])], existing=existing)
        write_library(updated, kwargs["library_path"])
        return updated

    monkeypatch.setattr(batch, "index_local_psarc", fake_index)
    report = batch.scan_changed_psarcs(
        dlc_root=dlc,
        rocksmith_root=rocksmith,
        workspace_root=workspace,
        library_path=library_path,
        source_resolver=lambda _: "unknown",
        limit=2,
    )
    assert report.planned_count == 2
    assert len(read_library(library_path).psarcs) == 2
