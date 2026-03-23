"""Tests for fuzzy matching in SemanticTagResolver (F09)."""

from unittest.mock import MagicMock

import pytest

from services.tools.geocoding.tag_resolver import SemanticTagResolver, TagCandidate


@pytest.fixture
def resolver_with_labels():
    """Create a resolver with mocked store containing tag labels."""
    r = SemanticTagResolver()
    r._store = MagicMock()
    r._store.is_initialized.return_value = True
    r._store.get_all_tag_labels.return_value = [
        "amenity=restaurant",
        "amenity=fast_food",
        "amenity=cafe",
        "building=residential",
        "building=apartments",
        "highway=bus_stop",
    ]
    return r


@pytest.mark.unit
def test_fuzzy_catches_typo(resolver_with_labels):
    results = resolver_with_labels._fuzzy_search("resturant")
    tags = [r.tag for r in results]
    assert "amenity=restaurant" in tags


@pytest.mark.unit
def test_fuzzy_catches_partial_match(resolver_with_labels):
    results = resolver_with_labels._fuzzy_search("restaurant")
    tags = [r.tag for r in results]
    assert "amenity=restaurant" in tags


@pytest.mark.unit
def test_fuzzy_returns_empty_when_no_match(resolver_with_labels):
    results = resolver_with_labels._fuzzy_search("xyznonexistent", min_score=90.0)
    assert len(results) == 0


@pytest.mark.unit
def test_fuzzy_normalizes_score(resolver_with_labels):
    """Scores should be in 0-1 range after normalization."""
    results = resolver_with_labels._fuzzy_search("restaurant")
    for r in results:
        assert 0.0 <= r.score <= 1.0


@pytest.mark.unit
def test_fuzzy_source_is_fuzzy(resolver_with_labels):
    results = resolver_with_labels._fuzzy_search("restaurant")
    for r in results:
        assert r.source == "fuzzy"


@pytest.mark.unit
def test_fuzzy_returns_empty_when_no_labels():
    r = SemanticTagResolver()
    r._store = MagicMock()
    r._store.is_initialized.return_value = True
    r._store.get_all_tag_labels.return_value = []
    results = r._fuzzy_search("restaurant")
    assert results == []


@pytest.mark.unit
def test_merge_deduplicates():
    resolver = SemanticTagResolver()
    fuzzy = [
        TagCandidate(
            key="amenity",
            value="restaurant",
            tag="amenity=restaurant",
            score=0.85,
            source="fuzzy",
        )
    ]
    vector = [
        TagCandidate(
            key="amenity",
            value="restaurant",
            tag="amenity=restaurant",
            score=0.92,
            source="vector",
        )
    ]
    merged = resolver._merge_candidates(fuzzy, vector)
    assert len(merged) == 1
    assert merged[0].source == "both"
    assert merged[0].score == 0.92  # higher score wins


@pytest.mark.unit
def test_merge_deduplicates_keeps_fuzzy_score_when_higher():
    resolver = SemanticTagResolver()
    fuzzy = [
        TagCandidate(
            key="amenity",
            value="restaurant",
            tag="amenity=restaurant",
            score=0.95,
            source="fuzzy",
        )
    ]
    vector = [
        TagCandidate(
            key="amenity",
            value="restaurant",
            tag="amenity=restaurant",
            score=0.80,
            source="vector",
        )
    ]
    merged = resolver._merge_candidates(fuzzy, vector)
    assert len(merged) == 1
    assert merged[0].source == "both"
    assert merged[0].score == 0.95  # fuzzy score wins here


@pytest.mark.unit
def test_merge_combines_unique():
    resolver = SemanticTagResolver()
    fuzzy = [
        TagCandidate(
            key="amenity",
            value="restaurant",
            tag="amenity=restaurant",
            score=0.85,
            source="fuzzy",
        )
    ]
    vector = [
        TagCandidate(
            key="amenity",
            value="cafe",
            tag="amenity=cafe",
            score=0.80,
            source="vector",
        )
    ]
    merged = resolver._merge_candidates(fuzzy, vector)
    assert len(merged) == 2


@pytest.mark.unit
def test_merge_sorted_by_score_descending():
    resolver = SemanticTagResolver()
    fuzzy = [
        TagCandidate(key="amenity", value="cafe", tag="amenity=cafe", score=0.70, source="fuzzy"),
    ]
    vector = [
        TagCandidate(
            key="amenity",
            value="restaurant",
            tag="amenity=restaurant",
            score=0.90,
            source="vector",
        ),
        TagCandidate(
            key="amenity",
            value="fast_food",
            tag="amenity=fast_food",
            score=0.80,
            source="vector",
        ),
    ]
    merged = resolver._merge_candidates(fuzzy, vector)
    scores = [c.score for c in merged]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.unit
def test_merge_empty_inputs():
    resolver = SemanticTagResolver()
    assert resolver._merge_candidates([], []) == []
    fuzzy = [TagCandidate(key="a", value="b", tag="a=b", score=0.8, source="fuzzy")]
    assert resolver._merge_candidates(fuzzy, []) == fuzzy
    vector = [TagCandidate(key="a", value="b", tag="a=b", score=0.8, source="vector")]
    assert resolver._merge_candidates([], vector) == vector
