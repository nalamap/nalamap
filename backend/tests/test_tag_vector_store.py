import pytest

from services.tools.geocoding.tag_vector_store import TagVectorStore, _tag_to_text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path):
    """Yield path to a temporary SQLite DB file."""
    db_file = tmp_path / "test_osm_tags.db"
    yield str(db_file)
    # tmp_path cleanup is automatic


@pytest.fixture
def store(temp_db):
    """Create a TagVectorStore backed by a temp DB."""
    return TagVectorStore(db_path=temp_db)


@pytest.fixture
def sample_tags():
    return [
        {
            "key": "building",
            "value": "residential",
            "description": "A residential building",
            "count_all": 5_000_000,
            "count_nodes": 0,
            "count_ways": 4_500_000,
            "count_relations": 500_000,
        },
        {
            "key": "building",
            "value": "apartments",
            "description": "A building with apartments",
            "count_all": 2_300_000,
            "count_nodes": 0,
            "count_ways": 2_100_000,
            "count_relations": 200_000,
        },
        {
            "key": "amenity",
            "value": "restaurant",
            "description": "A place to eat",
            "count_all": 700_000,
            "count_nodes": 600_000,
            "count_ways": 100_000,
            "count_relations": 0,
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_store_is_empty_initially(store):
    """A freshly created store should report empty state."""
    assert store.is_initialized() is False
    status = store.get_status()
    assert status["state"] == "empty"
    assert status["count"] == 0


@pytest.mark.unit
def test_store_tags_returns_count(store, sample_tags):
    """store_tags should return the number of tags stored."""
    count = store.store_tags(sample_tags)
    assert count == len(sample_tags)


@pytest.mark.unit
def test_store_status_after_population(store, sample_tags):
    """Status should reflect populated state after storing tags."""
    store.store_tags(sample_tags)
    status = store.get_status()
    assert status["state"] == "populated"
    assert status["count"] == len(sample_tags)


@pytest.mark.unit
def test_store_tags_and_search(store, sample_tags):
    """Similarity search should return relevant results after storing tags."""
    store.store_tags(sample_tags)
    results = store.similarity_search("residential building", k=5)
    assert len(results) > 0
    # The top result should be about buildings
    assert results[0]["key"] == "building"


@pytest.mark.unit
def test_similarity_search_result_fields(store, sample_tags):
    """Each search result must contain the required fields."""
    store.store_tags(sample_tags)
    results = store.similarity_search("cafe restaurant", k=3)
    assert len(results) > 0
    for r in results:
        assert "key" in r
        assert "value" in r
        assert "tag" in r
        assert "description" in r
        assert "count_all" in r
        assert "score" in r
        assert 0.0 <= r["score"] <= 1.0


@pytest.mark.unit
def test_min_count_filter(store, sample_tags):
    """min_count filter should exclude tags with low usage."""
    store.store_tags(sample_tags)
    # Only building=residential has count_all > 3M
    results = store.similarity_search("building", k=10, min_count=3_000_000)
    tags_returned = [r["tag"] for r in results]
    assert "amenity=restaurant" not in tags_returned
    assert "building=apartments" not in tags_returned


@pytest.mark.unit
def test_get_all_tag_labels(store, sample_tags):
    """get_all_tag_labels should return all 'key=value' strings."""
    store.store_tags(sample_tags)
    labels = store.get_all_tag_labels()
    assert "building=residential" in labels
    assert "building=apartments" in labels
    assert "amenity=restaurant" in labels
    assert len(labels) == len(sample_tags)


@pytest.mark.unit
def test_clear_store(store, sample_tags):
    """clear() should remove all tags and reset to empty state."""
    store.store_tags(sample_tags)
    assert store.is_initialized() is True
    store.clear()
    assert store.is_initialized() is False
    assert store.get_status()["count"] == 0


@pytest.mark.unit
def test_store_empty_list_returns_zero(store):
    """Storing an empty list should return 0 and leave the store empty."""
    count = store.store_tags([])
    assert count == 0
    assert store.is_initialized() is False


@pytest.mark.unit
def test_store_tags_without_description(store):
    """Tags without a description should still be stored successfully."""
    tags = [{"key": "highway", "value": "primary", "count_all": 1_000_000}]
    count = store.store_tags(tags)
    assert count == 1
    labels = store.get_all_tag_labels()
    assert "highway=primary" in labels


@pytest.mark.unit
def test_tag_text_with_description():
    """_tag_to_text should include description and count when description is set."""
    tag = {"key": "amenity", "value": "cafe", "description": "A cafe.", "count_all": 5000}
    text = _tag_to_text(tag)
    assert "amenity=cafe" in text
    assert "A cafe." in text
    assert "5000" in text


@pytest.mark.unit
def test_tag_text_without_description():
    """_tag_to_text should fall back to 'key=value' when no description."""
    tag = {"key": "amenity", "value": "cafe", "count_all": 5000}
    text = _tag_to_text(tag)
    assert text == "amenity=cafe"


@pytest.mark.unit
def test_tag_string_format(store, sample_tags):
    """Tags should be stored with correct 'key=value' tag string."""
    store.store_tags(sample_tags)
    labels = store.get_all_tag_labels()
    for tag in sample_tags:
        expected = f"{tag['key']}={tag['value']}"
        assert expected in labels
