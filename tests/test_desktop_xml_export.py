from pathlib import Path

import pytest

from rocksmith_cdlc_generator import desktop_xml_export


def test_bass_dispatch_uses_existing_validation_gated_exporter(tmp_path, monkeypatch):
    calls = []
    expected = {"xml": tmp_path / "eof" / "arr_bass_RS2.xml"}

    def fake_bass(project):
        calls.append(("bass", project))
        return expected

    monkeypatch.setattr(desktop_xml_export, "export_project_bass_authoring", fake_bass)

    result = desktop_xml_export.export_project_arrangement_xml(tmp_path, arrangement="bass")

    assert result == expected
    assert calls == [("bass", tmp_path.resolve())]


@pytest.mark.parametrize("arrangement", ["lead", "rhythm"])
def test_guitar_dispatch_preserves_arrangement_gate(tmp_path, monkeypatch, arrangement):
    calls = []
    expected = {"xml": tmp_path / "eof" / f"arr_{arrangement}_RS2.xml"}

    def fake_guitar(project, *, arrangement):
        calls.append((project, arrangement))
        return expected

    monkeypatch.setattr(desktop_xml_export, "export_project_guitar_authoring", fake_guitar)

    result = desktop_xml_export.export_project_arrangement_xml(tmp_path, arrangement=arrangement)

    assert result == expected
    assert calls == [(tmp_path.resolve(), arrangement)]


def test_unsupported_arrangement_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="Unsupported Rocksmith XML arrangement"):
        desktop_xml_export.export_project_arrangement_xml(tmp_path, arrangement="vocals")
