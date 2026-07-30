# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from chromadb import Client
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except ImportError:  # pragma: no cover
    Client = None
    Settings = None
    embedding_functions = None

LOGGER = logging.getLogger("ChromaVectorRepository")

DEFAULT_COLLECTION_NAME = "candidate_chunks"
DEFAULT_PERSIST_DIRECTORY = "./chroma"
DEFAULT_MODEL_NAME = "text-embedding-3-large"


class ChromaVectorRepository:
    """Simple ChromaDB wrapper for candidate CV chunk storage and retrieval."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or LOGGER
        if Client is None or Settings is None or embedding_functions is None:
            raise RuntimeError("chromadb is required for ChromaVectorRepository")

        self.collection_name = collection_name or DEFAULT_COLLECTION_NAME
        self.persist_directory = os.getenv("CHROMA_PERSIST_DIRECTORY", persist_directory or DEFAULT_PERSIST_DIRECTORY)
        self.model_name = os.getenv("OPENAI_EMBEDDING_MODEL", model_name or DEFAULT_MODEL_NAME)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for ChromaVectorRepository")

        self.client = Client(settings=Settings(is_persistent=True, persist_directory=self.persist_directory))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._build_embedding_function(),
        )

    def _build_embedding_function(self) -> Any:
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=self.api_key,
            model_name=self.model_name,
        )

    def upsert_chunks(
        self,
        chunks: List[Any],
        embeddings: List[Any],
        force_reindex: bool = False,
    ) -> int:
        if force_reindex:
            self.logger.info("Force reindex requested: clearing existing collection")
            self.collection.delete()
        else:
            candidate_ids = {chunk.candidate_id for chunk in chunks}
            for candidate_id in candidate_ids:
                self.collection.delete(where={"candidate_id": candidate_id})

        if not chunks or not embeddings:
            return 0

        embedding_by_chunk_id = {
            embedding.chunk_id: embedding for embedding in embeddings if getattr(embedding, "chunk_id", None)
        }
        filtered_chunks = [chunk for chunk in chunks if chunk.chunk_id in embedding_by_chunk_id]
        if not filtered_chunks:
            return 0

        ids = [chunk.chunk_id for chunk in filtered_chunks]
        vectors = [embedding_by_chunk_id[chunk.chunk_id].embedding for chunk in filtered_chunks]
        documents = [chunk.content for chunk in filtered_chunks]
        metadatas = [self._build_metadata(chunk, embedding_by_chunk_id[chunk.chunk_id]) for chunk in filtered_chunks]

        self.collection.upsert(ids=ids, embeddings=vectors, documents=documents, metadatas=metadatas)
        return len(ids)

    def query(self, query: str, k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not query:
            return []

        response = self.collection.query(
            query_texts=[query],
            n_results=k,
            where=filters or None,
            include=["documents", "metadatas", "distances"],
        )

        documents = self._flatten_query_result(response.get("documents", []))
        metadatas = self._flatten_query_result(response.get("metadatas", []))
        distances = self._flatten_query_result(response.get("distances", []))

        hits: List[Dict[str, Any]] = []
        for index, metadata in enumerate(metadatas):
            hit: Dict[str, Any] = {
                "content": documents[index] if index < len(documents) else "",
                **metadata,
                "similarity_score": self._normalize_similarity(distances[index]) if index < len(distances) else 0.0,
                "distance": distances[index] if index < len(distances) else None,
            }
            hits.append(hit)

        return hits

    def delete_candidate(self, candidate_id: str) -> int:
        result = self.collection.delete(where={"candidate_id": candidate_id})
        if isinstance(result, dict):
            return int(result.get("deleted", 0) or result.get("count", 0) or 0)
        return 0

    def get_candidate_chunks(self, candidate_id: str) -> List[Dict[str, Any]]:
        response = self.collection.get(
            where={"candidate_id": candidate_id},
            include=["documents", "metadatas"],
        )
        documents = self._flatten_query_result(response.get("documents", []))
        metadatas = self._flatten_query_result(response.get("metadatas", []))

        chunks: List[Dict[str, Any]] = []
        for index, metadata in enumerate(metadatas):
            chunks.append(
                {
                    "content": documents[index] if index < len(documents) else "",
                    **metadata,
                }
            )
        return chunks

    def count(self) -> int:
        result = self.collection.count()
        try:
            return int(result)
        except (TypeError, ValueError):
            return 0

    def _build_metadata(self, chunk: Any, embedding: Any) -> Dict[str, Any]:
        metadata = {
            "candidate_id": chunk.candidate_id,
            "source_file": chunk.source_file,
            "page": chunk.page,
            "section": chunk.section,
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            **(chunk.metadata or {}),
            **(embedding.metadata or {}),
        }
        return metadata

    def _flatten_query_result(self, result: Any) -> List[Any]:
        if isinstance(result, list) and result and isinstance(result[0], list):
            return result[0]
        return list(result) if result is not None else []

    def _normalize_similarity(self, distance: Any) -> float:
        try:
            value = float(distance)
            return max(0.0, 1.0 - value)
        except (TypeError, ValueError):
            return 0.0
