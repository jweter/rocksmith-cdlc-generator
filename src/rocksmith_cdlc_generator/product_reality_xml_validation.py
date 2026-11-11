from __future__ import annotations

from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .build_staging import BuildStageManifest
from .rocksmith_xml_structural_validation import structural_findings

XmlStructuralProductRealityStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED"]

_XML_ASSET_ROLE_SUFFIX = "_xml"
_XML_ASSET_ROLES = ("bass_xml", "lead_xml", "rhythm_xml")


class XmlRoleStructuralEvidence(BaseModel):
    """One arrangement's staged-XML structural self-consistency result.

    `role` is the arrangement role name ("bass"/"lead"/"rhythm"), not the staged
    asset role string, so a role-named acceptance item is only ever covered by that
    role's own result -- the same convention every other role-aware check in
    `private_product_reality.py` already follows.
    """

    model_config = ConfigDict(frozen=True)

    role: str
    status: XmlStructuralProductRealityStatus
    finding_count: int = Field(default=0, ge=0)
    message: str


class XmlStructuralProductRealityEvidence(BaseModel):
    """Sanitized deterministic Rocksmith XML structural self-consistency evidence.

    Re-parses whichever staged arrangement XML files `build_staging.stage_build`
    already wrote to disk and re-runs the same structural self-consistency check
    `rocksmith_xml.py` enforces before an in-memory tree is ever written, so passing
    this fact no longer silently depends on nobody having watched a build crash.
    This establishes only internal XML self-consistency (count attributes matching
    their actual children, required root elements present exactly once) -- it does
    not verify note/hash equality against the score or recording, which remain
    separate unestablished facts. Only arrangement roles, structural finding counts,
    and a generic message are reported -- no note content, lyrics, local paths, or
    other private song material leave the local evidence boundary.
    """

    model_config = ConfigDict(frozen=True)

    status: XmlStructuralProductRealityStatus
    roles: list[XmlRoleStructuralEvidence] = Field(default_factory=list)
    message: str


def _overall_status(
    roles: list[XmlRoleStructuralEvidence],
) -> XmlStructuralProductRealityStatus:
    statuses = {role.status for role in roles}
    if "FAIL" in statuses:
        return "FAIL"
    if "REVIEW_REQUIRED" in statuses:
        return "REVIEW_REQUIRED"
    return "PASS"


def collect_xml_structural_validation_evidence(
    project_dir: Path,
) -> XmlStructuralProductRealityEvidence:
    """Validate every staged arrangement XML asset's structural self-consistency.

    No staged build readiness manifest, or one without any staged arrangement XML, is
    REVIEW_REQUIRED rather than PASS: the runner cannot claim XML integrity without
    having anything to inspect. A missing staged file, malformed XML, or a structural
    defect is FAIL for that role; every other staged role is still checked
    independently rather than being short-circuited by one role's failure.
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

    roles: list[XmlRoleStructuralEvidence] = []
    for asset in xml_assets:
        role_name = asset.role.removesuffix(_XML_ASSET_ROLE_SUFFIX)
        path = Path(asset.path)
        if not path.is_file():
            roles.append(
                XmlRoleStructuralEvidence(
                    role=role_name,
                    status="FAIL",
                    message=f"Staged {asset.role} no longer exists at its registered path.",
                )
            )
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            roles.append(
                XmlRoleStructuralEvidence(
                    role=role_name,
                    status="FAIL",
                    message=f"Staged {asset.role} is not well-formed XML.",
                )
            )
            continue
        role_findings = structural_findings(root)
        if role_findings:
            roles.append(
                XmlRoleStructuralEvidence(
                    role=role_name,
                    status="FAIL",
                    finding_count=len(role_findings),
                    message=(
                        f"Staged {asset.role} failed structural self-consistency "
                        f"({len(role_findings)} finding(s))."
                    ),
                )
            )
        else:
            roles.append(
                XmlRoleStructuralEvidence(
                    role=role_name,
                    status="PASS",
                    message=f"Staged {asset.role} is structurally self-consistent.",
                )
            )

    status = _overall_status(roles)
    checked = ", ".join(role.role for role in roles)
    if status == "PASS":
        message = f"Staged arrangement XML ({checked}) is structurally self-consistent."
    else:
        failing = ", ".join(role.role for role in roles if role.status != "PASS")
        message = f"Staged arrangement XML failed structural self-consistency: {failing}."

    return XmlStructuralProductRealityEvidence(status=status, roles=roles, message=message)
