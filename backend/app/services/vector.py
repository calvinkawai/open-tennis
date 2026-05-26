import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import Settings, get_settings


COSINE_COLLECTION_METADATA = {"hnsw:space": "cosine"}
MAX_CONTEXTS_PER_SOURCE = 2
STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "and",
    "are",
    "ball",
    "can",
    "for",
    "from",
    "have",
    "hit",
    "how",
    "improve",
    "into",
    "more",
    "need",
    "shot",
    "that",
    "the",
    "this",
    "tennis",
    "with",
    "your",
}
QUERY_EXPANSIONS = {
    "weak": {"power", "speed", "drive", "force", "rotation"},
    "net": {"lift", "low", "high", "topspin", "clearance"},
    "under": {"lift", "low", "high", "topspin", "clearance"},
    "power": {"drive", "force", "rotation", "body", "legs"},
    "wrist": {"lag", "loose", "relaxed", "racket"},
    "topspin": {"low", "high", "brush", "windshield", "wiper"},
}


@dataclass(frozen=True)
class RetrievedContext:
    content: str
    source: str | None
    score: float | None = None
    rerank_score: float | None = None
    tutorial_title: str | None = None
    chunk_type: str | None = None
    segment_title: str | None = None
    key_coaching_cue: str | None = None
    visual_focus: str | None = None
    chunk_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorService:
    """Queries the local ChromaDB index for tennis technique context."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._vector_store: Chroma | None = None

    @property
    def vector_store(self) -> Chroma:
        if self._vector_store is None:
            self._vector_store = self._build_vector_store()
        return self._vector_store

    def search(self, query: str, k: int | None = None) -> list[RetrievedContext]:
        if not query.strip():
            raise ValueError("Query cannot be empty.")

        final_k = k or self.settings.retrieval_k
        fetch_k = max(final_k, self.settings.retrieval_fetch_k)
        results = self.vector_store.similarity_search_with_score(
            query.strip(),
            k=fetch_k,
        )
        contexts = [
            self._context_from_result(document, score)
            for document, score in results
        ]
        return self._rerank(query, contexts, final_k)

    def _build_vector_store(self) -> Chroma:
        chroma_path = Path(self.settings.chroma_db_path)
        if not chroma_path.exists():
            raise RuntimeError(f"ChromaDB path does not exist: {chroma_path}")

        embeddings = GoogleGenerativeAIEmbeddings(
            model=self.settings.embedding_model,
            google_api_key=self.settings.google_genai_api_key,
        )
        return Chroma(
            collection_name=self.settings.chroma_collection_name,
            persist_directory=str(chroma_path),
            embedding_function=embeddings,
            collection_metadata=COSINE_COLLECTION_METADATA,
        )

    def _context_from_result(self, document: Document, score: float) -> RetrievedContext:
        metadata = dict(document.metadata)
        return RetrievedContext(
            content=document.page_content,
            source=_metadata_str(metadata, "source"),
            score=score,
            tutorial_title=_metadata_str(metadata, "tutorial_title"),
            chunk_type=_metadata_str(metadata, "chunk_type"),
            segment_title=_metadata_str(metadata, "segment_title"),
            key_coaching_cue=_metadata_str(metadata, "key_coaching_cue"),
            visual_focus=_metadata_str(metadata, "visual_focus"),
            chunk_index=_metadata_int(metadata, "chunk_index"),
            metadata=metadata,
        )

    def _rerank(
        self,
        query: str,
        contexts: list[RetrievedContext],
        final_k: int,
    ) -> list[RetrievedContext]:
        query_tokens = _expand_query_tokens(_tokenize(query))
        scored_contexts = [
            (
                self._combined_score(context, query_tokens),
                context,
            )
            for context in contexts
        ]
        scored_contexts.sort(key=lambda item: item[0], reverse=True)

        source_counts: Counter[str] = Counter()
        selected: list[RetrievedContext] = []
        for rerank_score, context in scored_contexts:
            source_key = context.source or context.tutorial_title or "unknown"
            if source_counts[source_key] >= MAX_CONTEXTS_PER_SOURCE:
                continue
            selected.append(
                RetrievedContext(
                    content=context.content,
                    source=context.source,
                    score=context.score,
                    rerank_score=rerank_score,
                    tutorial_title=context.tutorial_title,
                    chunk_type=context.chunk_type,
                    segment_title=context.segment_title,
                    key_coaching_cue=context.key_coaching_cue,
                    visual_focus=context.visual_focus,
                    chunk_index=context.chunk_index,
                    metadata=context.metadata,
                )
            )
            source_counts[source_key] += 1
            if len(selected) == final_k:
                break

        return selected

    def _combined_score(
        self,
        context: RetrievedContext,
        query_tokens: set[str],
    ) -> float:
        vector_score = _distance_to_similarity(context.score)
        segment_title_score = _overlap_score(
            query_tokens,
            _tokenize(
                " ".join(
                    part
                    for part in [
                        context.chunk_type,
                        context.segment_title,
                    ]
                    if part
                )
            ),
        )
        topic_score = _overlap_score(
            query_tokens,
            _tokenize(context.tutorial_title or ""),
        )
        cue_score = _overlap_score(
            query_tokens,
            _tokenize(
                " ".join(
                    part
                    for part in [
                        context.key_coaching_cue,
                        context.visual_focus,
                    ]
                    if part
                )
            ),
        )
        content_score = _overlap_score(
            query_tokens,
            _tokenize(
                " ".join(
                    part
                    for part in [
                        context.content,
                    ]
                    if part
                )
            ),
        )
        segment_boost = 0.03 if context.chunk_type == "segment" else 0.0
        cue_boost = 0.02 if context.key_coaching_cue else 0.0
        return (
            vector_score
            + (0.24 * segment_title_score)
            + (0.04 * topic_score)
            + (0.10 * cue_score)
            + (0.08 * content_score)
            + segment_boost
            + cue_boost
        )


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _distance_to_similarity(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return 1.0 / (1.0 + max(distance, 0.0))


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if len(token) < 3 or token in STOPWORDS:
            continue
        tokens.add(token)
        if token.endswith("s") and len(token) > 4:
            tokens.add(token[:-1])
    return tokens


def _expand_query_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in tokens:
        expanded.update(QUERY_EXPANSIONS.get(token, set()))
    return expanded


def _overlap_score(query_tokens: set[str], document_tokens: set[str]) -> float:
    if not query_tokens or not document_tokens:
        return 0.0
    return len(query_tokens & document_tokens) / len(query_tokens)
