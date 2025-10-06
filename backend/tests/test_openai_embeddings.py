"""Test OpenAI embeddings integration with fallback behavior."""

import pytest

from services.tools.geoserver import vector_store as vs


@pytest.fixture(autouse=True)
def reset_store():
    """Clean up before and after each test."""
    vs.reset_vector_store_for_tests()
    yield
    vs.reset_vector_store_for_tests()


def test_openai_embeddings_fallback_when_not_configured():
    """Test that system falls back to hashing embeddings when OpenAI not configured."""
    # Get the embedding model (should use fallback since OpenAI not configured in tests)
    embedding_model = vs._get_embedding_model()

    # Should be either _HashingEmbeddings or _OpenAIEmbeddings with fallback enabled
    assert embedding_model is not None

    # Test that embeddings can be generated
    test_text = "Test layer for forest coverage analysis"
    embedding = embedding_model.embed_query(test_text)

    # Should produce a valid embedding vector
    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)

    # Test batch embedding
    texts = [
        "Forest coverage map",
        "Urban development zones",
        "Ocean bathymetry data",
    ]
    embeddings = embedding_model.embed_documents(texts)

    assert len(embeddings) == 3
    assert all(len(emb) > 0 for emb in embeddings)


def test_openai_embeddings_class_initialization():
    """Test that _OpenAIEmbeddings class can be instantiated."""
    # Import the class
    from services.tools.geoserver.vector_store import _OpenAIEmbeddings

    # Should initialize without errors (will use fallback since not configured)
    openai_embeddings = _OpenAIEmbeddings()

    # Should have fallback embeddings available
    assert openai_embeddings._fallback_embeddings is not None

    # Should be using fallback (since OpenAI not configured in tests)
    assert openai_embeddings._use_fallback is True

    # Should still produce embeddings via fallback
    test_text = "Earthquake risk assessment data"
    embedding = openai_embeddings.embed_query(test_text)

    assert isinstance(embedding, list)
    assert len(embedding) > 0


def test_embedding_consistency_across_calls():
    """Test that embeddings are consistent for the same text."""
    embedding_model = vs._get_embedding_model()

    text = "Consistent layer metadata test"

    # Generate embedding twice
    embedding1 = embedding_model.embed_query(text)
    embedding2 = embedding_model.embed_query(text)

    # Should be identical (deterministic for hashing embeddings)
    assert len(embedding1) == len(embedding2)
    assert embedding1 == embedding2


def test_embedding_model_singleton():
    """Test that embedding model is reused (singleton pattern)."""
    model1 = vs._get_embedding_model()
    model2 = vs._get_embedding_model()

    # Should be the same instance
    assert model1 is model2


def test_openai_class_has_required_methods():
    """Test that _OpenAIEmbeddings implements required Embeddings interface."""
    from services.tools.geoserver.vector_store import _OpenAIEmbeddings

    openai_embeddings = _OpenAIEmbeddings()

    # Check required methods exist
    assert hasattr(openai_embeddings, "embed_documents")
    assert hasattr(openai_embeddings, "embed_query")
    assert callable(openai_embeddings.embed_documents)
    assert callable(openai_embeddings.embed_query)

    # Check helper method exists
    assert hasattr(openai_embeddings, "_should_use_openai")
    assert callable(openai_embeddings._should_use_openai)
