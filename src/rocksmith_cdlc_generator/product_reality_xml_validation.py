from __future__ import annotations

from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .build_staging import BuildStageManifest
from .rocksmith_xml_structural_validation import structural_findings

XmlStructuralProductRealityStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED"]

_XML_ASSET_ROLES = ("bass_xml", "lead_xml", "rhythm_xml")


class XmlStructuralFindingSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    finding_count: int = Field(ge=1)


class XmlStructuralProductRealityEvidence(BaseModel):
    """Sanitized deterministic Rocksmith XML structural self-consistency evidence.

    Re-parses whichever staged arrangement XML files `build_staging.stage_build`
    already wrote to disk and re-runs the same structural self-consistency check
    `rocksmith_xml.py` enforces before an in-memory tree is ever written, so passing
    this fact no longer silently depends on nobody having watched a build crash. Only
    arrangement roles, structural finding counts, and a generic message are reported;
    no note content, lyrics, local paths, or other private song material leave the
    local evidence boundary.
    """

    model_config = ConfigDict(frozen=True)

    status: XmlStructuralProductRealityStatus
    roles_checked: list[str] = Field(default_factory=list)
    findings: list[XmlStructuralFindingSummary] = Field(default_factory=list)
    message: str


def collect_xml_structural_validation_evidence(
    project_dir: Path,
) -> XmlStructuralProductRealityEvidence:
    """Validate every staged arrangement XML asset's structural self-consistency.

    No staged build readiness manifest, or one without any staged arrangement XML, is
    REVIEW_REQUIRED rather than PASS: the runner cannot claim XML integrity without
    having anything to inspect. A missing staged file or a structural defect is FAIL.
    """

    readiness_path = project_dir / "build" / "staging" / "build_readiness.json"
    if not readiness_path.is_file():
        return XmlStructuralProductRealityEvidence(
            status="REVIEW_REQUIRED",
            message="No staged build readiness manifest is available for this project.",
        )

    try:
        manifest = BuildStageManifest.model_validate_json(
            readiness_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError, ValueError):
        return XmlStructuralProductRealityEvidence(
            status="REVIEW_REQUIRED",
            message="Staged build readiness manifest could not be read or validated.",
        )

    xml_assets = sorted(
        (asset for asset in manifest.assets if asset.role in _XML_ASSET_ROLES),
        key=lambda asset: asset.role,
    )
    if not xml_assets:
        return XmlStructuralProductRealityEvidence(
            status="REVIEW_REQUIRED",
            message="Staged build readiness manifest does not reference any arrangement XML.",
        )

    roles_checked: list[str] = []
    findings: list[XmlStructuralFindingSummary] = []
    for asset in xml_assets:
        path = Path(asset.path)
        if not path.is_file():
            return XmlStructuralProductRealityEvidence(
                status="FAIL",
                roles_checked=roles_checked,
                message=f"Staged {asset.role} no longer exists at its registered path.",
            )
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            return XmlStructuralProductRealityEvidence(
                status="FAIL",
                roles_checked=roles_checked,
                message=f"Staged {asset.role} is not well-formed XML.",
            )
        roles_checked.append(asset.role)
        role_findings = structural_findings(root)
        if role_findings:
            findings.append(
                XmlStructuralFindingSummary(
                    role=asset.role, finding_count=len(role_findings)
                )
            )

    if findings:
        summary = ", ".join(f"{item.role} ({item.finding_count})" for item in findings)
        return XmlStructuralProductRealityEvidence(
            status="FAIL",
            roles_checked=roles_checked,
            findings=findings,
            message=f"Staged arrangement XML failed structural self-consistency: {summary}.",
        )

    return XmlStructuralProductRealityEvidence(
        status="PASS",
        roles_checked=roles_checked,
        message="Staged arrangement XML ("
        + ", ".join(roles_checked)
        + ") is structurally self-consistent.",
    )
