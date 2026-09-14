from pathlib import Path
from types import SimpleNamespace

from rocksmith_cdlc_generator import private_product_reality_cli as cli


def test_mobile_review_cli_loads_authoritative_tempo_map_with_current_digest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "scenario.json"
    project_dir = tmp_path / "project"
    tempo_path = project_dir / "timing" / "tempo.json"
    tempo_map = object()

    monkeypatch.setattr(
        cli,
        "load_private_product_reality_scenario",
        lambda path: SimpleNamespace(project_dir=project_dir),
    )
    monkeypatch.setattr(cli, "authoritative_tempo_map_path", lambda project: tempo_path)
    monkeypatch.setattr(cli, "read_tempo_map", lambda path: tempo_map)
    monkeypatch.setattr(cli, "sha256_file", lambda path: "b" * 64)

    loaded_map, digest = cli._load_mobile_review_tempo_map(
        scenario_path,
        SimpleNamespace(tempo_map_sha256="a" * 64),
    )

    assert loaded_map is tempo_map
    assert digest == "b" * 64


def test_mobile_review_cli_skips_tempo_map_when_evidence_has_no_digest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli,
        "load_private_product_reality_scenario",
        lambda path: (_ for _ in ()).throw(AssertionError("scenario must not be loaded")),
    )

    loaded_map, digest = cli._load_mobile_review_tempo_map(
        tmp_path / "scenario.json",
        SimpleNamespace(tempo_map_sha256=None),
    )

    assert loaded_map is None
    assert digest is None
