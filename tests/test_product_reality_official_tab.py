from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.product_reality_official_tab as subject


def test_missing_registration_is_review_required_without_private_path(monkeypatch, tmp_path: Path) -> None:
    private_path = tmp_path / "private-song-project"

    def missing(_project_dir: Path):
        raise FileNotFoundError(str(private_path / "references" / "official-tab" / "manifest.json"))

    monkeypatch.setattr(subject, "verify_official_tab_registration", missing)

    evidence = subject.collect_official_tab_registration_evidence(private_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.checked_at_utc is None
    assert evidence.page_count is None
    assert evidence.drift_codes == []
    assert str(private_path) not in evidence.message


def test_verified_registration_maps_to_pass_without_private_details(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subject,
        "verify_official_tab_registration",
        lambda _project_dir: SimpleNamespace(
            status="PASS",
            checked_at_utc="2026-09-13T23:30:00+00:00",
            page_count=3,
            drift=[],
        ),
    )

    evidence = subject.collect_official_tab_registration_evidence(tmp_path)

    assert evidence.status == "PASS"
    assert evidence.checked_at_utc == "2026-09-13T23:30:00+00:00"
    assert evidence.page_count == 3
    assert evidence.drift_codes == []
    assert str(tmp_path) not in evidence.message


def test_registration_drift_maps_to_fail_with_sanitized_codes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subject,
        "verify_official_tab_registration",
        lambda _project_dir: SimpleNamespace(
            status="FAIL",
            checked_at_utc="2026-09-13T23:31:00+00:00",
            page_count=2,
            drift=[
                SimpleNamespace(code="page_hash_changed", message="private score path A"),
                SimpleNamespace(code="page_missing", message="private score path B"),
                SimpleNamespace(code="page_hash_changed", message="private score path C"),
            ],
        ),
    )

    evidence = subject.collect_official_tab_registration_evidence(tmp_path)

    assert evidence.status == "FAIL"
    assert evidence.page_count == 2
    assert evidence.drift_codes == ["page_hash_changed", "page_missing"]
    assert "private score path" not in evidence.message


def test_invalid_registration_evidence_is_review_required(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subject,
        "verify_official_tab_registration",
        lambda _project_dir: (_ for _ in ()).throw(ValueError("private malformed detail")),
    )

    evidence = subject.collect_official_tab_registration_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.page_count is None
    assert evidence.drift_codes == []
    assert "private malformed detail" not in evidence.message
