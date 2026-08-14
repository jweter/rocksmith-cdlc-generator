from __future__ import annotations

import json
import sys
from pathlib import Path

from rocksmith_cdlc_generator.source_inventory_cli import main


def test_source_inventory_cli_emits_json(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["cdlc-sources", str(project)])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["local_audio_sources"] == 0
    assert payload["local_symbolic_sources"] == 0
    assert payload["reference_count"] == 0
    assert payload["next_actions"]
