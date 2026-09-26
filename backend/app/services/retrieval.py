import hashlib
import logging
import threading
from dataclasses import dataclass
from typing import Protocol

import chromadb
from chromadb.api.types import PyEmbedding
from chromadb.config import Settings as ChromaSettings
from google import genai
from google.genai.errors import APIError
from google.genai.types import EmbedContentConfig, HttpOptions, HttpRetryOptions
from httpx import HTTPError

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.knowledge import EvidenceDetail
from app.services.wiki import WikiStore

logger = logging.getLogger(__name__)


class Embeddings(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class GeminiEmbeddings:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        if any(len(text) > 16000 for text in texts):
            raise AppError("EMBEDDING_BUDGET", "A source is too long for the configured embedding step.", 422)
        try:
            with genai.Client(
                api_key=self.settings.google_genai_api_key,
                http_options=HttpOptions(
                    timeout=int(self.settings.llm_timeout_seconds * 1000),
                    retry_options=HttpRetryOptions(attempts=self.settings.llm_max_retries + 1),
                ),
            ) as client:
                result = client.models.embed_content(
                    model=self.settings.embedding_model,
                    contents=texts,
                    config=EmbedContentConfig(task_type=task, auto_truncate=False),
                )
            if result.embeddings is None or len(result.embeddings) != len(texts):
                raise AppError("EMBEDDING_OUTPUT", "The embedding response was incomplete.", 502)
            vectors = []
            for embedding in result.embeddings:
                if not embedding.values:
                    raise AppError("EMBEDDING_OUTPUT", "The embedding response contained an empty vector.", 502)
                vectors.append(list(embedding.values))
            return vectors
        except (APIError, HTTPError, ValueError, RuntimeError, TimeoutError) as exc:
            logger.warning("embedding_failed", extra={"error_type": type(exc).__name__})
            raise AppError("EMBEDDING_UNAVAILABLE", "Semantic indexing is unavailable; local retrieval remains available.", 503) from exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


@dataclass(frozen=True)
class RetrievalResult:
    evidence: list[EvidenceDetail]
    mode: str
    warning: str | None = None


class WikiRetriever:
    def __init__(
        self, store: WikiStore, settings: Settings, embeddings: Embeddings | None = None
    ) -> None:
        self.store = store
        self.settings = settings
        self.embeddings = embeddings or GeminiEmbeddings(settings)
        self._collection = None
        self._failed_fingerprint: str | None = None
        self._lock = threading.Lock()

    @property
    def collection(self):
        if self._collection is None:
            client = chromadb.PersistentClient(
                path=str(self.settings.wiki_index_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                name="open_tennis_wiki_v1", metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def _eligible(self) -> list[EvidenceDetail]:
        return [
            item for item in self.store.list_indexable_evidence()
            if item.kind == "technical" or self.settings.allow_personal_model_context
        ]

    def _fingerprint(self, evidence: list[EvidenceDetail]) -> str:
        text = self.settings.embedding_model + "\n" + "\n".join(
            sorted(f"{item.id}:{item.revision}" for item in evidence)
        )
        return hashlib.sha256(text.encode()).hexdigest()

    def sync(self, force: bool = False) -> None:
        if not self.settings.semantic_index_enabled:
            return
        if not self._lock.acquire(blocking=False):
            if force:
                raise AppError("INDEX_BUSY", "Indexing is already running; wait for its result.", 409)
            return
        try:
            evidence = self._eligible()
            fingerprint = self._fingerprint(evidence)
            if self._failed_fingerprint == fingerprint and not force:
                return
            collection = self.collection
            if collection.metadata and collection.metadata.get("fingerprint") == fingerprint and not force:
                self._mark_pages("ready")
                return
            try:
                existing = set(collection.get(include=[])["ids"])
                active = {item.id for item in evidence}
                removed = sorted(existing - active)
                if removed:
                    collection.delete(ids=removed)
                unchanged_model = collection.metadata and collection.metadata.get("embedding_model") == self.settings.embedding_model
                missing = [item for item in evidence if item.id not in existing or not unchanged_model]
                for offset in range(0, len(missing), 32):
                    batch = missing[offset:offset + 32]
                    vectors = self.embeddings.embed_documents([item.excerpt for item in batch])
                    typed_vectors: list[PyEmbedding] = [vector for vector in vectors]
                    collection.upsert(
                        ids=[item.id for item in batch], embeddings=typed_vectors,
                        metadatas=[{"kind": item.kind, "revision": item.revision} for item in batch],
                    )
                collection.modify(metadata={
                    "fingerprint": fingerprint, "embedding_model": self.settings.embedding_model,
                })
                self._failed_fingerprint = None
                self._mark_pages("ready")
            except (AppError, ValueError, RuntimeError, OSError) as exc:
                self._failed_fingerprint = fingerprint
                self._mark_pages("failed")
                logger.warning("wiki_index_failed", extra={"error_type": type(exc).__name__})
                if isinstance(exc, AppError):
                    raise
                raise AppError("INDEX_UNAVAILABLE", "The semantic index failed; retry indexing explicitly.", 503) from exc
        finally:
            self._lock.release()

    def _mark_pages(self, status: str) -> None:
        for space in ("technical", "personal"):
            if space == "personal" and not self.settings.allow_personal_model_context:
                continue
            for page in self.store.list_pages(space):
                if page.version and page.index_status != status:
                    self.store.set_index_status(page.id, status)

    def search(
        self, query: str, page_id: str | None = None, include_personal: bool = False
    ) -> RetrievalResult:
        lexical = self.store.search_evidence(query, page_id, include_personal)
        if not self.settings.semantic_index_enabled:
            return RetrievalResult(lexical, "lexical", "当前使用本地文本检索；语义索引未启用。")
        try:
            eligible = self._eligible()
            collection = self.collection
            if not collection.metadata or collection.metadata.get("fingerprint") != self._fingerprint(eligible):
                return RetrievalResult(lexical, "lexical", "语义索引正在等待更新，本次使用本地文本检索。")
            if not eligible:
                return RetrievalResult([], "hybrid")
            current = {item.id: item for item in eligible if include_personal or item.kind == "technical"}
            if not current:
                return RetrievalResult(lexical, "hybrid")
            result = collection.query(
                query_embeddings=[self.embeddings.embed_query(query)],
                n_results=min(12, len(current)),
                where=None if include_personal else {"kind": "technical"},
                include=["distances"],
            )
            identifiers = result["ids"][0]
            distances = result["distances"][0] if result["distances"] else []
            semantic = [
                current[identifier] for identifier, distance in zip(identifiers, distances)
                if identifier in current and distance <= 0.5
            ]
            merged = {item.id: item for item in lexical + semantic}
            return RetrievalResult(list(merged.values())[:12], "hybrid")
        except (AppError, ValueError, RuntimeError, OSError) as exc:
            logger.warning("semantic_search_unavailable", extra={"error_type": type(exc).__name__})
            return RetrievalResult(lexical, "lexical", "语义检索失败，本次明确降级为本地文本检索。")
