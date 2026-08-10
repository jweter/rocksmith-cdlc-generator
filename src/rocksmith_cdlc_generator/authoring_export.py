from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .beats import read_tempo_map
from .fret_mapping import read_bass_mapping
from .guitar_authoring import GuitarAuthoringChart
from .guitar_validation import validate_guitar_project, write_guitar_review_artifacts
from .models import ProjectManifest
from .packaging_gate import PackagingBlockedError, require_packaging_ready
from .rocksmith_xml import (
    build_rocksmith_bass_xml,
    build_rocksmith_guitar_xml,
    write_rocksmith_xml,
)

GuitarArrangement = Literal["lead", "rhythm"]


class AuthoringExportManifest(BaseModel):
    schema_version: int = 1
    target: str = "rocksmith2014-xml"
    arrangement: str = "Bass"
    validation_status: str
    source_tempo_map: str
    source_mapping: str
    output_xml: str
    assumptions: list[str] = Field(default_factory=list)


class GuitarAuthoringExportManifest(BaseModel):
    schema_version: int = 1
    target: str = "rocksmith2014-xml"
    arrangement: str
    validation_status: str
    source_tempo_map: str
    source_chart: str
    output_xml: str
    assumptions: list[str] = Field(default_factory=list)


def export_project_bass_authoring(project_dir: Path) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    validation = require_packaging_ready(project_dir)

    tempo_path = project_dir / "analysis" / "tempo_map.json"
    mapping_path = project_dir / "charts" / "bass_mapped.json"
    manifest = ProjectManifest.load(project_dir)
    tempo_map = read_tempo_map(tempo_path)
    mapping = read_bass_mapping(mapping_path)

    export_dir = project_dir / "eof"
    xml_path = export_dir / "arr_bass_RS2.xml"
    manifest_path = export_dir / "export_manifest.json"
    readme_path = export_dir / "README.md"

    root = build_rocksmith_bass_xml(manifest, tempo_map, mapping)
    write_rocksmith_xml(root, xml_path)

    export_manifest = AuthoringExportManifest(
        validation_status=validation.status,
        source_tempo_map=str(tempo_path.relative_to(project_dir)),
        source_mapping=str(mapping_path.relative_to(project_dir)),
        output_xml=str(xml_path.relative_to(project_dir)),
        assumptions=[
            "Single full-song phrase and section are emitted because automatic section analysis is not implemented yet.",
            "No techniques, chords, anchors, tones, or Dynamic Difficulty are invented by this exporter.",
            "Time signature is taken directly from analysis/tempo_map.json.",
        ],
    )
    export_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(export_manifest.model_dump_json(indent=2), encoding="utf-8")
    readme_path.write_text(
        "# Rocksmith Authoring Export\n\n"
        "This directory contains a validation-gated Rocksmith 2014 arrangement XML generated from the canonical project data.\n\n"
        "- `arr_bass_RS2.xml`: single-level Bass arrangement XML (schema version 7).\n"
        "- `export_manifest.json`: provenance and explicit limitations.\n\n"
        "The XML intentionally omits inferred techniques, chords, anchors, tones, and Dynamic Difficulty. Review the arrangement in the normal Rocksmith authoring workflow before packaging.\n",
        encoding="utf-8",
    )

    return {
        "xml": xml_path,
        "manifest": manifest_path,
        "readme": readme_path,
    }


def export_project_guitar_authoring(
    project_dir: Path,
    *,
    arrangement: GuitarArrangement,
) -> dict[str, Path]:
    """Validate and export one Lead or Rhythm chart to Rocksmith 2014 XML."""
    project_dir = project_dir.resolve()
    validation = validate_guitar_project(project_dir, arrangement=arrangement)
    review_outputs = write_guitar_review_artifacts(
        validation,
        project_dir,
        arrangement=arrangement,
    )
    if not validation.can_package:
        codes = [item.code for item in validation.review_queue if item.severity == "FAIL"]
        detail = ", ".join(codes[:8]) or "validation_failed"
        raise PackagingBlockedError(
            f"{arrangement.capitalize()} validation is FAIL; export is blocked ({detail}). "
            f"Run `cdlc validate PROJECT --instrument {arrangement}` and resolve hard failures first."
        )

    tempo_path = project_dir / "analysis" / "tempo_map.json"
    chart_path = project_dir / "charts" / f"{arrangement}_source.json"
    manifest = ProjectManifest.load(project_dir)
    tempo_map = read_tempo_map(tempo_path)
    chart = GuitarAuthoringChart.model_validate_json(chart_path.read_text(encoding="utf-8"))

    export_dir = project_dir / "eof"
    xml_path = export_dir / f"arr_{arrangement}_RS2.xml"
    manifest_path = export_dir / f"{arrangement}_export_manifest.json"
    readme_path = export_dir / f"{arrangement.upper()}_README.md"

    root = build_rocksmith_guitar_xml(manifest, tempo_map, chart)
    write_rocksmith_xml(root, xml_path)

    export_manifest = GuitarAuthoringExportManifest(
        arrangement=arrangement.capitalize(),
        validation_status=validation.status,
        source_tempo_map=str(tempo_path.relative_to(project_dir)),
        source_chart=str(chart_path.relative_to(project_dir)),
        output_xml=str(xml_path.relative_to(project_dir)),
        assumptions=[
            "Single full-song phrase and section are emitted because automatic section analysis is not implemented yet.",
            "Chord names and left-hand fingering are not invented when the imported source does not provide verified values.",
            "Only technique semantics represented losslessly by the current Rocksmith XML bridge are emitted.",
            "Anchors, hand shapes, tones, and Dynamic Difficulty remain downstream authoring tasks.",
        ],
    )
    export_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(export_manifest.model_dump_json(indent=2), encoding="utf-8")
    readme_path.write_text(
        f"# Rocksmith {arrangement.capitalize()} Authoring Export\n\n"
        f"- `arr_{arrangement}_RS2.xml`: validation-gated schema-v7 {arrangement.capitalize()} arrangement.\n"
        f"- `{arrangement}_export_manifest.json`: source provenance and limitations.\n"
        f"- `../review/{arrangement}_validation_report.json`: arrangement-specific validation evidence.\n\n"
        "Review this XML in the normal Rocksmith authoring workflow before packaging. "
        "No unresolved string/fret positions are permitted through this export gate.\n",
        encoding="utf-8",
    )

    return {
        "xml": xml_path,
        "manifest": manifest_path,
        "readme": readme_path,
        "validation": review_outputs["validation"],
    }
