from pathlib import Path

import pytest

from rocksmith_cdlc_generator.private_library_corpus import (
    corpus_evidence_summary,
    hash_file,
    mirror_inventory,
    validate_mirror_boundaries,
)


def test_rejects_mirror_inside_live_library(tmp_path: Path) -> None:
    source = tmp_path / "Rocksmith" / "dlc"
    source.mkdir(parents=True)

    with pytest.raises(ValueError, match="non-overlapping"):
        validate_mirror_boundaries(source, source / "private-mirror")


def test_rejects_live_library_inside_mirror(tmp_path: Path) -> None:
    mirror = tmp_path / "private-mirror"
    source = mirror / "Rocksmith" / "dlc"
    source.mkdir(parents=True)

    with pytest.raises(ValueError, match="non-overlapping"):
        validate_mirror_boundaries(source, mirror)


def test_mirror_inventory_copies_and_hashes_without_mutating_source(tmp_path: Path) -> None:
    source = tmp_path / "live" / "dlc"
    mirror = tmp_path / "private" / "mirror"
    source.mkdir(parents=True)
    package = source / "Artist_Song_p.psarc"
    package.write_bytes(b"known package bytes")
    before = package.read_bytes()

    result = mirror_inventory(source, mirror)

    copied = mirror / package.name
    assert package.read_bytes() == before
    assert copied.read_bytes() == before
    assert result["corpus_schema_version"] == 1
    assert result["item_count"] == 1
    assert result["items"] == [
        {
            "relative_path": package.name,
            "sha256": hash_file(package),
            "size_bytes": len(before),
            "trust_tier": "C",
        }
    ]


def test_unknown_content_defaults_to_tier_c(tmp_path: Path) -> None:
    source = tmp_path / "live"
    mirror = tmp_path / "mirror"
    source.mkdir()
    (source / "unknown.psarc").write_bytes(b"x")

    result = mirror_inventory(source, mirror)

    assert result["items"][0]["trust_tier"] == "C"


def test_invalid_trust_tier_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "live"
    source.mkdir()

    with pytest.raises(ValueError, match="trust_tier"):
        mirror_inventory(source, tmp_path / "mirror", trust_tier="trusted")


def test_repository_safe_summary_does_not_expose_private_paths(tmp_path: Path) -> None:
    source = tmp_path / "live"
    mirror = tmp_path / "mirror"
    source.mkdir()
    package = source / "Private Artist - Private Song.psarc"
    package.write_bytes(b"private lawful package bytes")

    inventory = mirror_inventory(source, mirror)
    summary = corpus_evidence_summary(inventory)

    assert summary["corpus_evidence_schema_version"] == 1
    assert summary["item_count"] == 1
    assert summary["total_bytes"] == len(b"private lawful package bytes")
    assert summary["trust_tier_counts"] == {"A": 0, "B": 0, "C": 1}
    assert len(summary["corpus_sha256"]) == 64
    serialized = repr(summary)
    assert package.name not in serialized
    assert str(source) not in serialized
    assert "relative_path" not in serialized


def test_repository_safe_summary_fails_closed_on_malformed_inventory() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        corpus_evidence_summary(
            {
                "items": [
                    {
                        "relative_path": "private.psarc",
                        "sha256": "not-a-hash",
                        "size_bytes": 12,
                        "trust_tier": "C",
                    }
                ]
            }
        )
