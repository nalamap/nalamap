from __future__ import annotations

from typing import Iterable, List

from langchain_core.embeddings import Embeddings

from services.tools.geoserver import vector_store as vs


class DummyEmbeddings(Embeddings):
    def __init__(self) -> None:
        self.document_calls: List[List[str]] = []
        self.query_calls: List[str] = []

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:  # type: ignore[override]
        items = list(texts)
        self.document_calls.append(items)
        return [[float(index)] for index, _ in enumerate(items)]

    def embed_query(self, text: str) -> List[float]:  # type: ignore[override]
        self.query_calls.append(text)
        return [1.0]


def create_dummy_embeddings() -> DummyEmbeddings:
    return DummyEmbeddings()


def test_custom_embedding_factory(monkeypatch):
    vs.reset_vector_store_for_tests()
    monkeypatch.setenv(
        "NALAMAP_GEOSERVER_EMBEDDING_FACTORY",
        "tests.test_vector_store_embeddings:create_dummy_embeddings",
    )

    model = vs._get_embedding_model()
    assert model.__class__.__name__ == "DummyEmbeddings"
    assert model.__class__.__module__ == "tests.test_vector_store_embeddings"
    assert vs._get_embedding_model() is model

    # Clean up for other tests
    monkeypatch.delenv("NALAMAP_GEOSERVER_EMBEDDING_FACTORY", raising=False)
    vs.reset_vector_store_for_tests()
