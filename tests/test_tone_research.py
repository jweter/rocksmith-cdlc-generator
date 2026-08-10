from rocksmith_cdlc_generator.tone_research import (
    EffectClaim,
    GearClaim,
    SongIdentity,
    ToneEvidence,
    build_tone_research_plan,
    synthesize_tone_hypothesis,
)


def test_research_plan_prioritizes_track_album_and_direct_sources():
    plan = build_tone_research_plan(
        SongIdentity(artist="Example Band", title="Example Song", album="Example Album", year=1994)
    )

    labels = {query.label for query in plan.queries}
    assert "track-specific gear" in labels
    assert "album-specific gear" in labels
    assert "direct artist evidence" in labels
    assert "producer or studio evidence" in labels
    assert any("equipboard.com" in query.preferred_domains for query in plan.queries)


def test_track_artist_interview_outranks_artist_level_community_claim():
    song = SongIdentity(artist="Example Band", title="Example Song")
    evidence = [
        ToneEvidence(
            url="https://example.com/interview",
            title="Artist interview",
            kind="artist_interview",
            scope="track",
            basis="The guitarist identifies the amp used on the song.",
            gear=[GearClaim(category="amp", manufacturer="Marshall", model="JCM800")],
        ),
        ToneEvidence(
            url="https://example.net/forum",
            title="Forum speculation",
            kind="community_post",
            scope="artist",
            basis="A user believes the artist commonly uses another amp.",
            gear=[GearClaim(category="amp", manufacturer="Mesa", model="Dual Rectifier")],
        ),
    ]

    hypothesis = synthesize_tone_hypothesis(song, evidence)

    assert hypothesis.gear[0].model == "jcm800"
    assert hypothesis.gear[0].support_score > hypothesis.gear[1].support_score


def test_same_gear_claims_accumulate_across_independent_sources():
    song = SongIdentity(artist="Example Band", title="Example Song")
    evidence = [
        ToneEvidence(
            url="https://example.com/artist",
            title="Artist interview",
            kind="artist_interview",
            scope="album",
            basis="Artist names a Tube Screamer in the album sessions.",
            gear=[GearClaim(category="pedal", manufacturer="Ibanez", model="Tube Screamer")],
            effects=[EffectClaim(family="overdrive")],
        ),
        ToneEvidence(
            url="https://equipboard.com/example",
            title="Source-backed gear entry",
            kind="equipboard_submission",
            scope="album",
            basis="Equipboard entry cites album-session evidence.",
            gear=[GearClaim(category="pedal", manufacturer="Ibanez", model="Tube Screamer")],
            effects=[EffectClaim(family="overdrive")],
        ),
    ]

    hypothesis = synthesize_tone_hypothesis(song, evidence)

    assert len(hypothesis.gear) == 1
    assert hypothesis.gear[0].model == "tube screamer"
    assert len(hypothesis.gear[0].evidence_urls) == 2
    assert hypothesis.effects[0].family == "overdrive"
    assert len(hypothesis.effects[0].evidence_urls) == 2


def test_close_competing_gear_candidates_raise_warning():
    song = SongIdentity(artist="Example Band", title="Example Song")
    evidence = [
        ToneEvidence(
            url="https://example.com/a",
            title="Interview A",
            kind="artist_interview",
            scope="track",
            confidence=0.9,
            basis="Names amp A.",
            gear=[GearClaim(category="amp", model="Amp A", arrangement="lead")],
        ),
        ToneEvidence(
            url="https://example.com/b",
            title="Interview B",
            kind="producer_interview",
            scope="track",
            confidence=0.8,
            basis="Names amp B.",
            gear=[GearClaim(category="amp", model="Amp B", arrangement="lead")],
        ),
    ]

    hypothesis = synthesize_tone_hypothesis(song, evidence)

    assert hypothesis.warnings
    assert "Competing lead amp candidates" in hypothesis.warnings[0]


def test_tone_family_scores_are_normalized():
    song = SongIdentity(artist="Example Band", title="Example Song")
    hypothesis = synthesize_tone_hypothesis(
        song,
        [
            ToneEvidence(
                url="https://example.com/track",
                title="Track interview",
                kind="artist_interview",
                scope="track",
                basis="Artist describes the track as a high-gain sound.",
                tone_family="high_gain",
            ),
            ToneEvidence(
                url="https://example.com/album",
                title="Album feature",
                kind="studio_feature",
                scope="album",
                basis="Studio feature describes a crunchy album sound.",
                tone_family="crunch",
            ),
        ],
    )

    assert abs(sum(hypothesis.tone_families.values()) - 1.0) < 0.001
    assert hypothesis.tone_families["high_gain"] > hypothesis.tone_families["crunch"]
