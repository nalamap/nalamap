import pytest
from unittest.mock import MagicMock, patch

from services.tools.geocoding.tag_resolver import (
    SemanticTagResolver,
    TagResolution,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_raw_result(key, value, score=0.92, count_all=1_000_000, description=""):
    return {
        "key": key,
        "value": value,
        "tag": f"{key}={value}",
        "description": description,
        "count_all": count_all,
        "score": score,
    }


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.is_initialized.return_value = True
    store.similarity_search.return_value = [
        _make_raw_result("building", "residential", 0.94, 5_000_000, "A residential building"),
        _make_raw_result("building", "apartments", 0.91, 2_300_000, "Apartment building"),
        _make_raw_result("building", "house", 0.89, 1_800_000, "A house"),
    ]
    return store


@pytest.fixture
def resolver(mock_store):
    r = SemanticTagResolver()
    r._store = mock_store
    return r


@pytest.fixture
def many_candidates_store():
    """Store returning > 5 candidates (triggers LLM filter)."""
    store = MagicMock()
    store.is_initialized.return_value = True
    store.similarity_search.return_value = [
        _make_raw_result("building", f"v{i}", 0.85 - i * 0.01, 500_000) for i in range(8)
    ]
    return store


# ---------------------------------------------------------------------------
# Basic resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_returns_tags(resolver):
    """Should return a TagResolution with matched tags."""
    result = resolver.resolve("residential buildings", use_llm_refinement=False)
    assert result is not None
    assert isinstance(result, TagResolution)
    assert len(result.tags) == 3
    assert result.method == "semantic"


@pytest.mark.unit
def test_resolve_tags_have_key_and_value(resolver):
    """Each returned tag dict must have 'key' and 'value'."""
    result = resolver.resolve("residential buildings", use_llm_refinement=False)
    for tag in result.tags:
        assert "key" in tag
        assert "value" in tag


@pytest.mark.unit
def test_resolve_returns_none_when_store_not_initialized():
    """Should return None when the vector store is empty."""
    resolver = SemanticTagResolver()
    resolver._store = MagicMock()
    resolver._store.is_initialized.return_value = False
    result = resolver.resolve("anything")
    assert result is None


@pytest.mark.unit
def test_resolve_returns_empty_when_no_matches(resolver, mock_store):
    """Should return TagResolution with empty tags when search finds nothing."""
    mock_store.similarity_search.return_value = []
    result = resolver.resolve("xyznonexistent")
    assert result is not None
    assert len(result.tags) == 0


@pytest.mark.unit
def test_resolve_handles_exception_gracefully(resolver, mock_store):
    """Should return None on unexpected errors (DB crash etc.)."""
    mock_store.similarity_search.side_effect = Exception("DB error")
    result = resolver.resolve("anything")
    assert result is None


# ---------------------------------------------------------------------------
# min_similarity filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_filters_by_min_similarity(resolver, mock_store):
    """Tags below min_similarity threshold must be excluded."""
    mock_store.similarity_search.return_value = [
        _make_raw_result("building", "residential", 0.94, 5_000_000),
        _make_raw_result("landuse", "residential", 0.50, 1_000_000),  # below threshold
    ]
    result = resolver.resolve("residential buildings", use_llm_refinement=False)
    assert len(result.tags) == 1
    assert result.tags[0]["key"] == "building"


@pytest.mark.unit
def test_resolve_no_tags_when_all_below_threshold(resolver, mock_store):
    """All tags below threshold → empty result, not None."""
    mock_store.similarity_search.return_value = [
        _make_raw_result("building", "residential", 0.30, 5_000_000),
    ]
    result = resolver.resolve("something", use_llm_refinement=False)
    assert result is not None
    assert len(result.tags) == 0


# ---------------------------------------------------------------------------
# candidates_considered
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_candidates_considered_is_set(resolver):
    """candidates_considered should reflect how many passed the score filter."""
    result = resolver.resolve("residential buildings", use_llm_refinement=False)
    assert result.candidates_considered == 3


# ---------------------------------------------------------------------------
# LLM refinement
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_llm_filter_not_called_with_few_candidates(resolver, mock_store):
    """LLM filter must NOT be called when candidates <= 5."""
    with patch.object(resolver, "_llm_filter") as mock_llm:
        resolver.resolve("residential buildings", use_llm_refinement=True)
    mock_llm.assert_not_called()


@pytest.mark.unit
def test_llm_filter_called_with_many_candidates(many_candidates_store):
    """LLM filter must be called when candidates > 5 and use_llm_refinement=True."""
    resolver = SemanticTagResolver()
    resolver._store = many_candidates_store

    with patch.object(resolver, "_llm_filter", return_value=([], [])) as mock_llm:
        resolver.resolve("buildings", use_llm_refinement=True)
    mock_llm.assert_called_once()


@pytest.mark.unit
def test_llm_filter_fallback_on_no_api_key(many_candidates_store):
    """LLM filter should silently fall back to all candidates when no API key."""
    resolver = SemanticTagResolver()
    resolver._store = many_candidates_store

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key-not-set"}):
        result = resolver.resolve("buildings", use_llm_refinement=True)

    assert result is not None
    # All 8 candidates are returned (no LLM filtering)
    assert len(result.tags) == 8


@pytest.mark.unit
def test_llm_filter_fallback_on_api_error(many_candidates_store):
    """LLM filter failure must return all candidates, not raise."""
    resolver = SemanticTagResolver()
    resolver._store = many_candidates_store

    with patch("services.tools.geocoding.tag_resolver.os.getenv", return_value="sk-real-key"):
        with patch("services.tools.geocoding.tag_resolver.json.loads", side_effect=ValueError):
            with patch("openai.OpenAI"):
                result = resolver.resolve("buildings", use_llm_refinement=True)

    assert result is not None


@pytest.mark.unit
def test_llm_filter_selects_and_excludes():
    """LLM filter should correctly split candidates into selected and excluded."""
    store = MagicMock()
    store.is_initialized.return_value = True
    store.similarity_search.return_value = [
        _make_raw_result("building", f"v{i}", 0.85, 500_000) for i in range(6)
    ]
    resolver = SemanticTagResolver()
    resolver._store = store

    llm_response = {
        "selected": ["building=v0", "building=v1"],
        "excluded": [{"tag": "building=v2", "reason": "wrong type"}],
    }

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-real-key"}):
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value.choices[0].message.content = (
                json.dumps(llm_response)
            )

            result = resolver.resolve("buildings", use_llm_refinement=True)

    # selected explicitly + unmentioned candidates included by default
    assert {"key": "building", "value": "v0"} in result.tags
    assert {"key": "building", "value": "v1"} in result.tags
    # excluded tag should not be in result.tags
    assert {"key": "building", "value": "v2"} not in result.tags
    # excluded should be tracked
    assert any(e["tag"] == "building=v2" for e in result.excluded)


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_explanation_is_human_readable(resolver):
    """Explanation must contain user intent and at least one resolved tag."""
    result = resolver.resolve("residential buildings", use_llm_refinement=False)
    assert "residential buildings" in result.explanation
    assert "building=residential" in result.explanation


@pytest.mark.unit
def test_explanation_truncates_long_tag_list():
    """For > 6 tags, explanation must indicate count rather than listing all."""
    store = MagicMock()
    store.is_initialized.return_value = True
    store.similarity_search.return_value = [
        _make_raw_result("building", f"v{i}", 0.85, 500_000) for i in range(8)
    ]
    resolver = SemanticTagResolver()
    resolver._store = store

    result = resolver.resolve("buildings", use_llm_refinement=False)
    assert "8 total" in result.explanation


# ---------------------------------------------------------------------------
# detail field
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detail_without_llm(resolver):
    result = resolver.resolve("buildings", use_llm_refinement=False)
    assert "tag embeddings" in result.detail
    assert "LLM" not in result.detail


import json  # noqa: E402 — keep import at bottom to not confuse test ordering
