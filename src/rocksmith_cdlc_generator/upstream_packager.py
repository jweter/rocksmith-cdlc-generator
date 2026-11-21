"""Opt-in, pinned auto-cdlc cdlc-pack adapter behind our existing PSARC gates.

No upstream executable or audio is bundled, downloaded, updated, or uploaded here.
The user's pinned local cdlc-pack.exe is treated as an untrusted build process;
the generator's own registration/inspection gates determine package readiness.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .build_staging import (
    BuildStageManifest,
    PsarcReceipt,
    _require_same_readiness,
    register_psarc,
    stage_build,
    verify_psarc_registration,
)
from .hashing import sha256_file
from .psarc_inspection import bridge_available


def build_psarc_with_cdlc_pack(
    project_dir: Path,
    *,
    packager: Path,
    expected_packager_sha256: str,
    wwise: Path | None = None,
    dlcbuilder_project: Path | None = None,
    timeout_seconds: int = 3600,
) -> Path:
    """Build into private project staging, then independently inspect and register.

    Only the official, explicitly supplied executable path is run; no shell,
    installer, implicit download, network reporting, or live Rocksmith writes.
    The returned path is a local PSARC receipt, never an installation action.
    """
    project_dir = project_dir.resolve()
    executable = packager.expanduser().resolve()
    if not executable.is_file() or executable.suffix.lower() != ".exe":
        raise FileNotFoundError(f"Provide an existing local cdlc-pack .exe: {executable}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_packager_sha256):
        raise ValueError("Expected packager SHA-256 must be 64 lowercase hex characters")
    executable_sha256 = sha256_file(executable)
    if executable_sha256 != expected_packager_sha256:
        raise ValueError("Packager binary SHA-256 differs from the pinned expected hash")
    if wwise is not None:
        wwise = wwise.expanduser().resolve()
        if not wwise.is_file():
            raise FileNotFoundError(f"Wwise executable not found: {wwise}")
    if not 1 <= timeout_seconds <= 14400:
        raise ValueError("Packaging timeout must be between 1 and 14400 seconds")
    if not bridge_available():
        raise RuntimeError(
            "Deep PSARC inspection bridge is required for unattended packaging. "
            "Run scripts/bootstrap_psarc_bridge.ps1 or configure ROCKSMITH_PSARC_BRIDGE."
        )

    readiness_path = stage_build(project_dir, dlcbuilder_project=dlcbuilder_project)
    manifest = BuildStageManifest.model_validate_json(readiness_path.read_text(encoding="utf-8"))
    readiness_sha256 = sha256_file(readiness_path)
    output_dir = readiness_path.parent / "cdlc_pack_output"
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path = readiness_path.parent / "cdlc_pack_run.json"
    command = [str(executable), manifest.dlcbuilder_project, "--salida", str(output_dir)]
    if wwise is not None:
        command.extend(["--wwise", str(wwise)])

    report: dict[str, object] = {
        "schema_version": 1,
        "status": "FAIL",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "packager_name": executable.name,
        "packager_sha256": executable_sha256,
        "package_generation": manifest.package_generation,
        "readiness_sha256": readiness_sha256,
        "output_directory": str(output_dir),
        "live_rocksmith_install_modified": False,
        "command_exit_code": None,
    }
    try:
        try:
            completed = subprocess.run(
                command, cwd=str(project_dir), capture_output=True, text=True,
                encoding="utf-8", errors="replace", check=False, timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"cdlc-pack timed out after {timeout_seconds} seconds") from exc

        report["command_exit_code"] = completed.returncode
        report["stdout_tail"] = completed.stdout[-16384:]
        report["stderr_tail"] = completed.stderr[-16384:]
        if completed.returncode != 0:
            raise RuntimeError(f"cdlc-pack exited with code {completed.returncode}; see local run report")
        if any(line.strip().startswith("VERIF error=") for line in completed.stdout.splitlines()):
            raise RuntimeError("cdlc-pack reported a PSARC read-back verification error")

        # Upstream may log read-back failures yet still exit successfully. Never
        # trust its exit code or its printed VERIF lines as acceptance evidence.
        _require_same_readiness(
            project_dir,
            expected_generation=manifest.package_generation,
            expected_readiness_sha256=readiness_sha256,
        )
        packages = sorted(
            path for path in output_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".psarc"
        )
        if len(packages) != 1 or not packages[0].name.lower().endswith("_p.psarc"):
            raise ValueError(
                "Expected exactly one newly built PC *_p.psarc in private output; "
                f"found {len(packages)} PSARC file(s)"
            )

        receipt_path = register_psarc(project_dir, packages[0])
        receipt = PsarcReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
        verification = verify_psarc_registration(project_dir)
        if (
            receipt.package_generation != manifest.package_generation
            or receipt.content_inspection_status != "PASS"
            or not receipt.safe_for_manual_installation
            or verification.status != "PASS"
        ):
            raise RuntimeError("Independent deep PSARC registration verification did not PASS")
        report["status"] = "PASS"
        report["receipt_path"] = str(receipt_path)
        report["staged_psarc_sha256"] = receipt.sha256
        report["content_inspection_status"] = receipt.content_inspection_status
        return receipt_path
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        # This evidence remains private/local and is not included in public CI.
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
