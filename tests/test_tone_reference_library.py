from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_library import (
    LocalToneReference,
    ReferenceToneComponent,
    ToneReferenceLibrary,
    changed_psarcs,
    merge_scan_results,
)


def _tone(path: Path, *, source_type: str = "unknown", arrangement: str = "lead") -> LocalToneReference:
    return LocalToneReference(
        source_psarc_sha256="0" * 64,
        source_path=str(path),
        source_type=source_type,
        artist="Artist",
        title="Song",
        arrangement=arrangement,
        tone_key="tone_a",
        tone_descriptors=["high_gain", "delay"],
        components=[
            ReferenceToneComponent(slot="Amp", device_key="amp-1"),
            ReferenceToneComponent(slot="Rack1", device_key="delay-1", knob_values={"Time": 0.4}),
        ],
    )


def test_fingerprint_is_stable_for_component_order(tmp_path: Path) -> None:
    path = tmp_path / "song.psarc"
    first = _tone(path)
    second = first.model_copy(update={"components": list(reversed(first.components))})
    assert first.fingerprint == second.fingerprint


def test_changed_psarcs_detects_new_and_unchanged_files(tmp_path: Path) -> None:
    source = tmp_path / "dlc"
    source.mkdir()
    psarc = source / "song_p.psarc"
    psarc.write_bytes(b"PSAR-test")

    assert changed_psarcs(source) == [psarc]
    library = merge_scan_results(source, [(psarc, "official_rocksmith", [_tone(psarc)])])
    assert changed_psarcs(source, library) == []


def test_merge_replaces_changed_file_and_removes_deleted_files(tmp_path: Path) -> None:
    source = tmp_path / "dlc"
    source.mkdir()
    keep = source / "keep_p.psarc"
    gone = source / "gone_p.psarc"
    keep.write_bytes(b"keep-one")
    gone.write_bytes(b"gone")

    library = merge_scan_results(
        source,
        [
            (keep, "official_rocksmith", [_tone(keep)]),
            (gone, "custom_dlc", [_tone(gone, source_type="custom_dlc")]),
        ],
    )
    assert len(library.psarcs) == 2
    old_keep_hash = next(item.sha256 for item in library.psarcs if Path(item.path).name == "keep_p.psarc")

    gone.unlink()
    keep.write_bytes(b"keep-two")
    updated = merge_scan_results(source, [(keep, "official_rocksmith", [_tone(keep)])], library)
    assert [Path(item.path).name for item in updated.psarcs] == ["keep_p.psarc"]
    assert len(updated.tones) == 1
    assert updated.psarcs[0].sha256 != old_keep_hash


def test_official_references_rank_above_custom_for_equal_match(tmp_path: Path) -> None:
    official = _tone(tmp_path / "official.psarc", source_type="official_rocksmith")
    custom = _tone(tmp_path / "custom.psarc", source_type="custom_dlc")
    library = ToneReferenceLibrary(scan_root=str(tmp_path), tones=[custom, official])

    ranked = library.find_similar(
        arrangement="lead",
        device_keys={"amp-1", "delay-1"},
        descriptors={"high_gain", "delay"},
    )
    assert ranked[0][1].source_type == "official_rocksmith"
    assert ranked[0][0] > ranked[1][0]


def test_arrangements_are_not_cross_ranked(tmp_path: Path) -> None:
    lead = _tone(tmp_path / "lead.psarc", source_type="official_rocksmith", arrangement="lead")
    bass = _tone(tmp_path / "bass.psarc", source_type="official_rocksmith", arrangement="bass")
    library = ToneReferenceLibrary(scan_root=str(tmp_path), tones=[lead, bass])

    ranked = library.find_similar(arrangement="bass", device_keys={"amp-1"})
    assert len(ranked) == 1
    assert ranked[0][1].arrangement == "bass"
