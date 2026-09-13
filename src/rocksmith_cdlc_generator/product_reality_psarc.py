from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .build_staging import verify_psarc_registration

PsarcProductRealityStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED"]


class PsarcProductRealityEvidence(BaseModel):
    """Sanitized deterministic PSARC registration evidence for Product Reality.

    This deliberately omits local/private paths and file contents. The detailed
    registration verifier remains the authority for on-disk inspection; this model
    is the safe summary that can be embedded into broader Product Reality evidence.
    """

    model_config = ConfigDict(frozen=True)

    status: PsarcProductRealityStatus
    checked_at_utc: str | None = None
    drift_codes: list[str] = Field(default_factory=list)
    message: str


def collect_psarc_registration_evidence(project_dir: Path) -> PsarcProductRealityEvidence:
    """Map PSARC registration verification into privacy-safe Product Reality evidence.

    A missing or unreadable receipt is REVIEW_REQUIRED rather than PASS: the runner
    cannot claim packaging integrity without registration evidence. Once a receipt
    exists, missing registered inputs are deterministic registration drift and must
    fail closed as FAIL rather than being downgraded to REVIEW_REQUIRED. No local
    paths or private source material are copied into the returned evidence.
    """

    receipt_path = project_dir / "build" / "staging" / "psarc_receipt.json"
    receipt_exists = receipt_path.is_file()

    try:
        verification = verify_psarc_registration(project_dir)
    except FileNotFoundError:
        if receipt_exists:
            return PsarcProductRealityEvidence(
                status="FAIL",
                drift_codes=["registered_input_missing"],
                message="A registered PSARC input is missing from the current project state.",
            )
        return PsarcProductRealityEvidence(
            status="REVIEW_REQUIRED",
            message="PSARC registration evidence is not available for this project.",
        )
    except (OSError, ValueError):
        return PsarcProductRealityEvidence(
            status="REVIEW_REQUIRED",
            message="PSARC registration evidence could not be read or validated.",
        )

    drift_codes = sorted({item.code for item in verification.drift})
    if verification.status == "FAIL":
        return PsarcProductRealityEvidence(
            status="FAIL",
            checked_at_utc=verification.checked_at_utc,
            drift_codes=drift_codes,
            message="PSARC registration drift was detected against current project state.",
        )

    return PsarcProductRealityEvidence(
        status="PASS",
        checked_at_utc=verification.checked_at_utc,
        message="PSARC registration matches current project state.",
    )
