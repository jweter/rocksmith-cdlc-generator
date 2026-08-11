from pathlib import Path

from rocksmith_cdlc_generator.tone_corpus_diagnostics import diagnose_similarity, summarize_library
from rocksmith_cdlc_generator.tone_reference_library import (
    LocalToneReference,
    ReferenceToneComponent,
    ScannedPsarcRecord,
    ToneReferenceLibrary,
)


def _tone(path: Path, *, source_type: str, arrangement: str = "lead", key: str = "amp-1") -> LocalToneReference:
    return LocalToneReference(
        source_psarc_sha256="0" * 64,
        source_path=str(path),
        source_type=source_type,
        artist="Artist",
        title="Song",
        arrangement=arrangement,
        tone_key=f"tone-{key}",
        tone_descriptors=["High_Gain", "Delay"],
        components=[ReferenceToneComponent(slot="Amp", device_key=key)],
    )


def test_summarize_library_reports_counts_and_duplicates(tmp_path: Path) -> None:
    path_a = tmp_path / "a.psarc"
    path_b = tmp_path / "b.psarc"
    official = _tone(path_a, source_type="official_rocksmith")
    duplicate = official.model_copy(update={"source_path": str(path_b), "source_type": "custom_dlc"})
    bass = _tone(path_b, source_type="custom_dlc", arrangement="bass", key="bass-1")
    library = ToneReferenceLibrary(
        scan_root=str(tmp_path),
        psarcs=[
            ScannedPsarcRecord(path=str(path_a), sha256="1" * 64, size_bytes=1, modified_ns=1, source_type="official_rocksmith", tone_count=1),
            ScannedPsarcRecord(path=str(path_b), sha256="2" * 64, size_bytes=1, modified_ns=1, source_type="custom_dlc", tone_count=2),
        ],
        tones=[official, duplicate, bass],
    )

    stats = summarize_library(library)
    assert stats.psarc_count == 2
    assert stats.tone_count == 3
    assert stats.official_tone_count == 1
    assert stats.source_counts == {"custom_dlc": 2, "official_rocksmith": 1}
    assert stats.arrangement_counts == {"bass": 1, "lead": 2}
    assert stats.unique_fingerprint_count == 2
    assert stats.duplicate_tone_count == 1
    assert stats.device_key_counts["amp-1"] == 2
    assert stats.descriptor_counts["high_gain"] == 3


def test_similarity_diagnostics_explain_score_components(tmp_path: Path) -> None:
    official = _tone(tmp_path / "official.psarc", source_type="official_rocksmith")
    custom = _tone(tmp_path / "custom.psarc", source_type="custom_dlc")
    library = ToneReferenceLibrary(scan_root=str(tmp_path), tones=[custom, official])

    matches = diagnose_similarity(
        library,
        arrangement="lead",
        device_keys={"amp-1", "missing"},
        descriptors={"high_gain", "delay"},
    )
    assert matches[0].tone.source_type == "official_rocksmith"
    assert matches[0].matched_device_keys == ("amp-1",)
    assert matches[0].matched_descriptors == ("delay", "high_gain")
    assert matches[0].key_overlap == 0.5
    assert matches[0].descriptor_overlap == 1.0
    assert matches[0].authority_weight == 1.0
    assert matches[0].score > matches[1].score


def test_similarity_diagnostics_keep_arrangement_roles_isolated(tmp_path: Path) -> None:
    lead = _tone(tmp_path / "lead.psarc", source_type="official_rocksmith", arrangement="lead")
    bass = _tone(tmp_path / "bass.psarc", source_type="official_rocksmith", arrangement="bass")
    library = ToneReferenceLibrary(scan_root=str(tmp_path), tones=[lead, bass])

    matches = diagnose_similarity(library, arrangement="bass", device_keys={"bass-1"})
    assert len(matches) == 1
    assert matches[0].tone.arrangement == "bass"
