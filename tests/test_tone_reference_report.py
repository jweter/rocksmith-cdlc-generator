from __future__ import annotations

from rocksmith_cdlc_generator.tone_reference_recommendations import (
    ArrangementReferenceEvidence,
    RecommendedReferenceComponent,
    ToneRecommendationEvidenceReport,
    ToneReferenceCandidate,
)
from rocksmith_cdlc_generator.tone_reference_report import (
    render_tone_reference_markdown,
    write_tone_reference_report_bundle,
)


def _report() -> ToneRecommendationEvidenceReport:
    return ToneRecommendationEvidenceReport(
        artist="Example Artist",
        title="Example Song",
        bound_plan_sha256="a" * 64,
        library_scan_root="C:/private/rocksmith-tone-library",
        library_psarc_count=10,
        library_tone_count=24,
        arrangements=[
            ArrangementReferenceEvidence(
                arrangement="lead",
                label="Lead",
                query_device_keys=["amp_key"],
                candidates=[
                    ToneReferenceCandidate(
                        score=0.81,
                        authority_weight=1.0,
                        source_type="official_rocksmith",
                        source_path="C:/Rocksmith2014/dlc/example.psarc",
                        source_psarc_sha256="b" * 64,
                        artist="Reference Artist",
                        title="Reference Song",
                        tone_key="tone_a",
                        tone_name="Lead Tone",
                        fingerprint="c" * 64,
                        matched_device_keys=["amp_key"],
                        descriptors=["high gain"],
                        components=[
                            RecommendedReferenceComponent(
                                slot="Amp",
                                device_key="amp_key",
                                device_name="Example Amp",
                                device_type="Amp",
                                knob_values={"Gain": 0.7, "Treble": 0.6},
                            )
                        ],
                    )
                ],
            )
        ],
    )


def test_markdown_report_is_explicitly_review_only() -> None:
    markdown = render_tone_reference_markdown(_report())

    assert "Human review is required" in markdown
    assert "Automatic apply permitted: **no**" in markdown
    assert "official_rocksmith" in markdown
    assert "amp_key" in markdown
    assert "Gain=0.7" in markdown
    assert "does not mutate the bound tone plan" in markdown


def test_report_bundle_writes_json_and_markdown(tmp_path) -> None:
    json_path, markdown_path = write_tone_reference_report_bundle(_report(), tmp_path)

    assert json_path.exists()
    assert markdown_path.exists()
    assert json_path.name == "example-artist-example-song-tone-reference-evidence.json"
    assert markdown_path.name == "example-artist-example-song-tone-reference-evidence.md"
    assert '"can_auto_apply": false' in json_path.read_text(encoding="utf-8")
    assert "Evidence only" in markdown_path.read_text(encoding="utf-8")
