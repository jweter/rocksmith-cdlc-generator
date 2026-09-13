from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.product_reality_psarc as subject


def test_missing_registration_is_review_required_without_private_path(monkeypatch, tmp_path: Path) -> None:
    private_path = tmp_path / "private-song-project"

    def missing(_project_dir: Path):
        raise FileNotFoundError(str(private_path / "build" / "staging" / "psarc_receipt.json"))

    monkeypatch.setattr(subject, "verify_psarc_registration", missing)

    evidence = subject.collect_psarc_registration_evidence(private_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.checked_at_utc is None
    assert evidence.drift_codes == []
    assert str(private_path) not in evidence.message


def test_missing_registered_input_is_fail_without_private_path(monkeypatch, tmp_path: Path) -> None:
    private_path = tmp_path / "private-song-project"
    receipt = private_path / "build" / "staging" / "psarc_receipt.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text("{}", encoding="utf-8")

    def missing_input(_project_dir: Path):
        raise FileNotFoundError(str(private_path / "build" / "dlcbuilder" / "missing.xml"))

    monkeypatch.setattr(subject, "verify_psarc_registration", missing_input)

    evidence = subject.collect_psarc_registration_evidence(private_path)

    assert evidence.status == "FAIL"
    assert evidence.checked_at_utc is None
    assert evidence.drift_codes == ["registered_input_missing"]
    assert str(private_path) not in evidence.message


def test_verified_registration_maps_to_pass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subject,
        "verify_psarc_registration",
        lambda _project_dir: SimpleNamespace(
            status="PASS",
            checked_at_utc="2026-09-13T10:00:00+00:00",
            drift=[],
        ),
    )

    evidence = subject.collect_psarc_registration_evidence(tmp_path)

    assert evidence.status == "PASS"
    assert evidence.checked_at_utc == "2026-09-13T10:00:00+00:00"
    assert evidence.drift_codes == []


def test_registration_drift_maps_to_fail_with_sanitized_codes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subject,
        "verify_psarc_registration",
        lambda _project_dir: SimpleNamespace(
            status="FAIL",
            checked_at_utc="2026-09-13T10:01:00+00:00",
            drift=[
                SimpleNamespace(code="input_asset_changed", message="private path A"),
                SimpleNamespace(code="psarc_hash_changed", message="private path B"),
                SimpleNamespace(code="input_asset_changed", message="private path C"),
            ],
        ),
    )

    evidence = subject.collect_psarc_registration_evidence(tmp_path)

    assert evidence.status == "FAIL"
    assert evidence.drift_codes == ["input_asset_changed", "psarc_hash_changed"]
    assert "private path" not in evidence.message


def test_invalid_registration_evidence_is_review_required(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subject,
        "verify_psarc_registration",
        lambda _project_dir: (_ for _ in ()).throw(ValueError("private malformed detail")),
    )

    evidence = subject.collect_psarc_registration_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.drift_codes == []
    assert "private malformed detail" not in evidence.message
