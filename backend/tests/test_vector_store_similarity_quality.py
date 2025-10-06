"""Test the quality of similarity search with improved embeddings.

This test demonstrates how the enhanced embedding approach improves
semantic matching compared to simple hash-based embeddings.
"""

import pytest

from models.geodata import DataOrigin, DataType, GeoDataObject
from services.tools.geoserver import vector_store as vs


def make_layer(
    layer_id: str,
    name: str,
    title: str,
    description: str,
    layer_type: str = "WMS",
    data_source: str = "TestGeoServer",
    base_url: str = "https://example.com/geoserver",
) -> GeoDataObject:
    """Helper to create test GeoDataObject instances."""
    return GeoDataObject(
        id=layer_id,
        data_source_id="test-catalog",
        data_type=DataType.LAYER,
        data_origin=DataOrigin.TOOL,
        data_source=data_source,
        data_link=f"{base_url}/{layer_id}",
        name=name,
        title=title,
        description=description,
        layer_type=layer_type,
    )


@pytest.fixture(autouse=True)
def reset_store():
    """Clean up before and after each test."""
    vs.reset_vector_store_for_tests()
    yield
    vs.reset_vector_store_for_tests()


def test_similarity_search_matches_semantically_related_terms():
    """Test that similar concepts have higher similarity scores.

    With the improved embeddings:
    1. Important fields (title, name) get higher weight
    2. Stopwords are filtered out
    3. N-grams help with partial matches
    4. TF-IDF weighting helps distinguish important terms
    """
    session_id = "test-semantic-search"
    backend_url = "https://example.com/geoserver"

    # Store layers with related but different terminology
    layers = [
        make_layer(
            layer_id="1",
            name="forest_cover",
            title="Forest Coverage Map",
            description="Detailed mapping of forested areas and woodland regions",
        ),
        make_layer(
            layer_id="2",
            name="urban_areas",
            title="Urban Development Zones",
            description="City boundaries and metropolitan areas with population density",
        ),
        make_layer(
            layer_id="3",
            name="tree_density",
            title="Tree Canopy and Density",
            description="Analysis of tree coverage and woodland density metrics",
        ),
        make_layer(
            layer_id="4",
            name="ocean_depth",
            title="Bathymetric Ocean Data",
            description="Underwater topography and seafloor elevation measurements",
        ),
    ]

    vs.store_layers(session_id, backend_url, "Test Server", layers)

    # Query for forest-related data
    forest_results = vs.similarity_search(
        session_id=session_id,
        backend_urls=[backend_url],
        query="forest woodland trees",
        limit=4,
    )

    # The top 2 results should be forest-related layers
    # (forest_cover and tree_density), not ocean or urban
    assert len(forest_results) >= 2

    forest_related_names = {"forest_cover", "tree_density"}
    top_2_names = {layer.name for layer, _ in forest_results[:2]}

    # At least one of the top 2 should be forest-related
    # (with improved embeddings, should be both)
    assert (
        len(top_2_names & forest_related_names) >= 1
    ), f"Expected forest-related layers in top 2, got {top_2_names}"


def test_title_weighting_prioritizes_exact_matches():
    """Test that title matches rank higher than description matches.

    With 3x weighting on titles, layers with query terms in the title
    should rank higher than those with terms only in description.
    """
    session_id = "test-title-priority"
    backend_url = "https://example.com/geoserver"

    layers = [
        make_layer(
            layer_id="a",
            name="layer_a",
            title="Earthquake Risk Assessment",
            description="Various geological data including seismic activity",
        ),
        make_layer(
            layer_id="b",
            name="layer_b",
            title="Historical Weather Patterns",
            description="Earthquake zones and fault lines from historical records",
        ),
    ]

    vs.store_layers(session_id, backend_url, "Test Server", layers)

    # Query for earthquake data
    results = vs.similarity_search(
        session_id=session_id,
        backend_urls=[backend_url],
        query="earthquake",
        limit=2,
    )

    # Layer with "earthquake" in title should rank first
    assert (
        results[0][0].name == "layer_a"
    ), "Title matches should rank higher than description matches"


def test_stopword_filtering_improves_relevance():
    """Test that stopwords don't dominate similarity scores.

    With stopword filtering, content words should matter more than
    common words like "the", "and", "of", etc.
    """
    session_id = "test-stopwords"
    backend_url = "https://example.com/geoserver"

    layers = [
        make_layer(
            layer_id="precip",
            name="precipitation",
            title="Precipitation Data",
            description="Annual rainfall and precipitation patterns",
        ),
        make_layer(
            layer_id="unrelated",
            name="unrelated",
            title="The Analysis of the Data from the System",
            description="The various measurements of the values in the database",
        ),
    ]

    vs.store_layers(session_id, backend_url, "Test Server", layers)

    # Query with meaningful content words
    results = vs.similarity_search(
        session_id=session_id,
        backend_urls=[backend_url],
        query="precipitation rainfall",
        limit=2,
    )

    # Despite "unrelated" having many common words,
    # "precipitation" should rank first due to content word matching
    assert (
        results[0][0].name == "precipitation"
    ), "Content words should matter more than stopwords"


def test_ngram_support_for_partial_matches():
    """Test that n-grams help match partial or compound terms.

    With character trigram support, queries can match parts of words,
    helping with typos or related terms.
    """
    session_id = "test-ngrams"
    backend_url = "https://example.com/geoserver"

    layers = [
        make_layer(
            layer_id="wildfire",
            name="wildfire_risk",
            title="Wildfire Risk Assessment",
            description="Areas prone to wildfires and fire hazard zones",
        ),
        make_layer(
            layer_id="wind",
            name="wind_patterns",
            title="Wind Speed and Direction",
            description="Meteorological wind data and air circulation patterns",
        ),
    ]

    vs.store_layers(session_id, backend_url, "Test Server", layers)

    # Query with "fire" should match "wildfire" via n-grams
    results = vs.similarity_search(
        session_id=session_id,
        backend_urls=[backend_url],
        query="fire risk",
        limit=2,
    )

    # Wildfire layer should rank higher than wind patterns
    assert (
        results[0][0].name == "wildfire_risk"
    ), "N-grams should help match 'fire' within 'wildfire'"
