"""Semantic tag resolver: maps natural-language user intent to OSM tags.

Multi-stage pipeline:
1. Vector similarity search against the tag vector store (F02)
2. Optional LLM refinement to filter/rank candidates

Falls back gracefully at every stage — if the vector store is not yet
populated, the caller is expected to use the existing LLM-based expansion
(_expand_tags_with_llm in geocoding.py).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TagCandidate:
    """A candidate OSM tag with relevance score."""

    key: str
    value: str
    tag: str  # "key=value"
    description: str = ""
    count_all: int = 0
    score: float = 0.0
    source: str = ""  # "vector", "fuzzy", "both"


@dataclass
class TagResolution:
    """Result of semantic tag resolution."""

    tags: List[Dict[str, str]]  # [{"key": "building", "value": "residential"}, ...]
    explanation: str = ""
    method: str = ""  # "semantic", "llm_expansion", "direct_match"
    detail: str = ""  # "expanded via tag embeddings + LLM"
    candidates_considered: int = 0
    excluded: List[Dict[str, str]] = field(default_factory=list)
    # [{"tag": "landuse=residential", "reason": "land zoning, not buildings"}]


class SemanticTagResolver:
    """Resolves natural-language user intent to a set of OSM tags.

    Uses a multi-stage pipeline:
    1. Vector similarity search (sqlite-vec) for semantic candidates
    2. Optional LLM refinement for disambiguation

    Falls back gracefully if the vector store is not initialized.
    """

    def __init__(self) -> None:
        self._store = None  # lazy init

    def _get_store(self):
        """Lazy-load the TagVectorStore singleton."""
        if self._store is None:
            from services.tools.geocoding.tag_vector_store import TagVectorStore

            self._store = TagVectorStore()
        return self._store

    def resolve(
        self,
        user_intent: str,
        max_candidates: int = 30,
        min_similarity: float = 0.65,
        min_tag_count: int = 100,
        use_llm_refinement: bool = True,
    ) -> Optional[TagResolution]:
        """Resolve user intent to OSM tags.

        Returns None if the vector store is not initialized (caller should
        fall back to _expand_tags_with_llm from Phase A).
        """
        store = self._get_store()
        if not store.is_initialized():
            logger.info("Tag vector store not initialized, falling back to Phase A")
            return None

        try:
            # Stage 1a: Fuzzy matching (sub-ms, catches typos and lexical near-matches)
            fuzzy_candidates = self._fuzzy_search(user_intent)

            # Stage 1b: Vector similarity search (semantic)
            vector_candidates = self._vector_search(
                user_intent, max_candidates, min_similarity, min_tag_count
            )

            # Stage 1c: Merge and deduplicate
            candidates = self._merge_candidates(fuzzy_candidates, vector_candidates)

            if not candidates:
                return TagResolution(
                    tags=[],
                    explanation="No matching OSM tags found.",
                    method="semantic",
                    detail="No vector matches above similarity threshold",
                )

            # Stage 2: LLM refinement (only when there are many candidates)
            excluded: List[Tuple[TagCandidate, str]] = []
            if use_llm_refinement and len(candidates) > 5:
                selected, excluded = self._llm_filter(user_intent, candidates)
            else:
                selected = candidates

            tags = [{"key": c.key, "value": c.value} for c in selected]
            used_llm = use_llm_refinement and len(candidates) > 5

            return TagResolution(
                tags=tags,
                explanation=self._build_explanation(user_intent, selected, excluded),
                method="semantic",
                detail="expanded via tag embeddings" + (" + LLM" if used_llm else ""),
                candidates_considered=len(candidates),
                excluded=[{"tag": c.tag, "reason": r} for c, r in excluded],
            )

        except Exception as e:
            logger.warning("Semantic tag resolution failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Stage 1: vector search
    # ------------------------------------------------------------------

    def _vector_search(
        self,
        query: str,
        max_candidates: int,
        min_similarity: float,
        min_tag_count: int,
    ) -> List[TagCandidate]:
        """Run vector similarity search against the tag store."""
        store = self._get_store()
        raw_results = store.similarity_search(query, k=max_candidates, min_count=min_tag_count)
        return [
            TagCandidate(
                key=r["key"],
                value=r["value"],
                tag=r["tag"],
                description=r.get("description", ""),
                count_all=r.get("count_all", 0),
                score=r.get("score", 0.0),
                source="vector",
            )
            for r in raw_results
            if r.get("score", 0.0) >= min_similarity
        ]

    def _fuzzy_search(
        self, query: str, limit: int = 10, min_score: float = 70.0
    ) -> List[TagCandidate]:
        """Search for tags using fuzzy string matching (RapidFuzz).

        Catches typos and lexical near-matches. Complements vector search
        which handles semantic similarity.

        Uses RapidFuzz WRatio scorer (weighted ratio) which handles:
        - Partial matches ("restaurant" matches "amenity=restaurant")
        - Reordered tokens ("bus stop" matches "highway=bus_stop")
        - Typos ("resturant" matches "amenity=restaurant")

        Returns empty list if rapidfuzz is not installed (graceful degradation).
        """
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            logger.debug("rapidfuzz not installed, skipping fuzzy matching")
            return []

        store = self._get_store()
        all_labels = store.get_all_tag_labels()  # ["amenity=restaurant", ...]

        if not all_labels:
            return []

        matches = process.extract(
            query,
            all_labels,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=min_score,
        )

        candidates = []
        for tag_str, score, _ in matches:
            key, value = tag_str.split("=", 1)
            candidates.append(
                TagCandidate(
                    key=key,
                    value=value,
                    tag=tag_str,
                    score=score / 100.0,  # Normalize to 0-1 range
                    source="fuzzy",
                )
            )
        return candidates

    def _merge_candidates(
        self, fuzzy: List[TagCandidate], vector: List[TagCandidate]
    ) -> List[TagCandidate]:
        """Merge fuzzy and vector candidates, deduplicating by tag string.

        When a tag appears in both lists:
        - Use the higher score
        - Mark source as "both"

        Sort by score descending.
        """
        by_tag: Dict[str, TagCandidate] = {}
        for c in fuzzy:
            by_tag[c.tag] = c

        for c in vector:
            if c.tag in by_tag:
                existing = by_tag[c.tag]
                if c.score > existing.score:
                    c.source = "both"
                    by_tag[c.tag] = c
                else:
                    existing.source = "both"
            else:
                by_tag[c.tag] = c

        return sorted(by_tag.values(), key=lambda c: c.score, reverse=True)

    # ------------------------------------------------------------------
    # Stage 2: LLM filter
    # ------------------------------------------------------------------

    def _llm_filter(
        self,
        user_intent: str,
        candidates: List[TagCandidate],
    ) -> Tuple[List[TagCandidate], List[Tuple[TagCandidate, str]]]:
        """Use an LLM to filter candidates to only relevant tags.

        Asks the LLM to select which candidates match the user intent and
        briefly explain any exclusions.

        Returns: (selected_candidates, [(excluded_candidate, reason), ...])
        On any failure, returns all candidates unfiltered.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-test-key-not-set":
            logger.debug("No OpenAI API key — skipping LLM filter stage")
            return candidates, []

        try:
            from openai import OpenAI

            candidate_lines = "\n".join(
                f'  - "{c.tag}": {c.description or "(no description)"}' for c in candidates
            )
            prompt = (
                f'You are an OpenStreetMap expert. The user wants to find: "{user_intent}"\n\n'
                "From the following OSM tag candidates, select ONLY those that are directly "
                "relevant to the user intent. Exclude tags for unrelated concepts.\n\n"
                f"Candidates:\n{candidate_lines}\n\n"
                "Respond ONLY with valid JSON in this exact format:\n"
                '{"selected": ["tag1=value1", "tag2=value2"], '
                '"excluded": [{"tag": "tag3=value3", "reason": "short reason"}]}'
            )

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)

            selected_tags = set(data.get("selected", []))
            excluded_map = {
                e["tag"]: e.get("reason", "")
                for e in data.get("excluded", [])
                if isinstance(e, dict) and "tag" in e
            }

            selected: List[TagCandidate] = []
            excluded: List[Tuple[TagCandidate, str]] = []

            for c in candidates:
                if c.tag in selected_tags:
                    selected.append(c)
                elif c.tag in excluded_map:
                    excluded.append((c, excluded_map[c.tag]))
                else:
                    # LLM didn't mention it — include by default
                    selected.append(c)

            if not selected:
                # LLM returned nothing useful — fall back to all candidates
                logger.warning("LLM filter returned empty selection, using all candidates")
                return candidates, []

            logger.info(
                "LLM filter: %d → %d selected, %d excluded",
                len(candidates),
                len(selected),
                len(excluded),
            )
            return selected, excluded

        except Exception as e:
            logger.warning("LLM filter stage failed, using all candidates: %s", e)
            return candidates, []

    # ------------------------------------------------------------------
    # Explanation builder
    # ------------------------------------------------------------------

    def _build_explanation(
        self,
        user_intent: str,
        selected: List[TagCandidate],
        excluded: List[Tuple[TagCandidate, str]],
    ) -> str:
        """Build a human-readable explanation of the resolution."""
        tag_count = len(selected)
        tag_summary = ", ".join(c.tag for c in selected[:6])
        if tag_count > 6:
            tag_summary += f", ... ({tag_count} total)"
        return f"Resolved '{user_intent}' to {tag_count} OSM tags: {tag_summary}"
