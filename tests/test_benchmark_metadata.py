from __future__ import annotations

from rocksmith_cdlc_generator.benchmark_metadata import (
    BenchmarkCatalogMetadata,
    BenchmarkMetadataQuery,
    enrich_benchmark_metadata,
)


class FakeProvider:
    name = "fake-catalog"

    def lookup(self, query: BenchmarkMetadataQuery) -> BenchmarkCatalogMetadata | None:
        return BenchmarkCatalogMetadata(
            provider=self.name,
            provider_track_id="track-123",
            artist=query.artist,
            title=query.title,
            album="Example Album",
            duration_seconds=210.5,
            isrc="USABC1200001",
            source_page_url="https://example.org/catalog/track-123",
        )


class EmptyProvider:
    name = "empty"

    def lookup(self, query: BenchmarkMetadataQuery) -> BenchmarkCatalogMetadata | None:
        return None


def test_enrichment_returns_human_review_gated_receipt() -> None:
    query = BenchmarkMetadataQuery(
        benchmark_id="BMARK-001",
        artist="Lamb of God",
        title="Laid to Rest",
    )

    receipt = enrich_benchmark_metadata(query, FakeProvider())

    assert receipt is not None
    assert receipt.benchmark_id == "BMARK-001"
    assert receipt.metadata.provider == "fake-catalog"
    assert receipt.metadata.duration_seconds == 210.5
    assert receipt.human_review_required is True


def test_enrichment_allows_no_confident_provider_match() -> None:
    query = BenchmarkMetadataQuery(
        benchmark_id="BMARK-020",
        artist="Lamb of God",
        title="Walk With Me in Hell",
    )

    assert enrich_benchmark_metadata(query, EmptyProvider()) is None


def test_provider_identity_mismatch_is_rejected() -> None:
    class MismatchedProvider(FakeProvider):
        name = "expected-provider"

        def lookup(self, query: BenchmarkMetadataQuery) -> BenchmarkCatalogMetadata | None:
            result = super().lookup(query)
            assert result is not None
            return result.model_copy(update={"provider": "unexpected-provider"})

    query = BenchmarkMetadataQuery(
        benchmark_id="BMARK-002",
        artist="Trivium",
        title="Built to Fall",
    )

    try:
        enrich_benchmark_metadata(query, MismatchedProvider())
    except ValueError as exc:
        assert "provider result name" in str(exc)
    else:
        raise AssertionError("provider identity mismatch should be rejected")
