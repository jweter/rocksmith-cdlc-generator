from rocksmith_cdlc_generator.packaged_reference_sets import (
    BWV1007_BASS_DROPD_MANIFEST,
    bwv1007_bass_dropd_manifest_path,
    packaged_reference_manifest,
)
from rocksmith_cdlc_generator.private_score_bundle import PrivateScoreBundleSpec


def test_bwv1007_public_safe_manifest_is_available_in_source_checkout() -> None:
    path = bwv1007_bass_dropd_manifest_path()
    assert path.name == BWV1007_BASS_DROPD_MANIFEST
    spec = PrivateScoreBundleSpec.read_yaml(path)
    assert spec.bundle_id == "BWV1007_Bass_DropD"
    assert spec.instrument == "bass"
    assert spec.tuning_midi == [38, 45, 50, 55]
    assert spec.movements[0].movement_id == "prelude"


def test_packaged_reference_locator_rejects_unapproved_filename() -> None:
    try:
        packaged_reference_manifest("private-score-page.jpeg")
    except FileNotFoundError as exc:
        assert "unknown packaged reference manifest" in str(exc)
    else:
        raise AssertionError("unapproved packaged reference filename was accepted")
