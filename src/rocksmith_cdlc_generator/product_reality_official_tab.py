from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .official_tab_reference import verify_official_tab_registration

OfficialTabProductRealityStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED"]


class OfficialTabProductRealityEvidence(BaseModel):
    """Privacy-safe official TAB registration evidence for Product Reality.

    The underlying verifier inspects private project-local reference pages. This
    projection deliberately exposes only status, timestamp, page count, drift codes,
    and a generic message: no local paths, hashes, images, mappings, or private score
    contents leave the local evidence boundary.
    """

    model_config = ConfigDict(frozen=True)

    status: OfficialTabProductRealityStatus
    checked_at_utc: str | None = None
    page_count: int | None = Field(default=None, ge=1)
    drift_codes: list[str] = Field(default_factory=list)
    message: str


def collect_official_tab_registration_evidence(
    project_dir: Path,
) -> OfficialTabProductRealityEvidence:
    """Map official TAB persistence verification into sanitized Product Reality evidence.

    No registered pages is REVIEW_REQUIRED, never PASS. Once pages are registered,
    deterministic file/path/hash/decodability drift is FAIL. The detailed verifier
    remains authoritative and this adapter never includes private paths or score data.
    """

    try:
        verification = verify_official_tab_registration(project_dir)
    except FileNotFoundError:
        return OfficialTabProductRealityEvidence(
            status="REVIEW_REQUIRED",
            message="Official TAB registration evidence is not available for this project.",
        )
    except (OSError, ValueError, ValidationError):
        return OfficialTabProductRealityEvidence(
            status="REVIEW_REQUIRED",
            message="Official TAB registration evidence could not be read or validated.",
        )

    drift_codes = sorted({item.code for item in verification.drift})
    if verification.status == "FAIL":
        return OfficialTabProductRealityEvidence(
            status="FAIL",
            checked_at_utc=verification.checked_at_utc,
            page_count=verification.page_count,
            drift_codes=drift_codes,
            message="Official TAB registration drift was detected against current project state.",
        )

    return OfficialTabProductRealityEvidence(
        status="PASS",
        checked_at_utc=verification.checked_at_utc,
        page_count=verification.page_count,
        message="Official TAB registration matches current project state.",
    )
