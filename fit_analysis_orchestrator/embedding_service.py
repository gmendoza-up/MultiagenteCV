# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models import DocumentChunk, EmbeddingResult

try:
    from openai import OpenAI as AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None

LOGGER = logging.getLogger("EmbeddingService")

DEFAULT_MODEL = "text-embedding-3-large"
DEFAULT_BATCH_SIZE = 16
DEFAULT_CONCURRENCY = 4


class EmbeddingService:
    def __init__(
        self,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        concurrency: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or LOGGER
        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", model or DEFAULT_MODEL)
        self.batch_size = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", str(batch_size or DEFAULT_BATCH_SIZE))))
        self.concurrency = max(1, int(os.getenv("EMBEDDING_CONCURRENCY", str(concurrency or DEFAULT_CONCURRENCY))))
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.semaphore = asyncio.Semaphore(self.concurrency)

    async def generate_embeddings(self, chunks: List[DocumentChunk]) -> List[EmbeddingResult]:
        if not chunks:
            return []

        batch_groups = self._batch_chunks(chunks)
        tasks = [asyncio.create_task(self._process_batch(batch)) for batch in batch_groups]
        results = await asyncio.gather(*tasks)
        return [item for batch_result in results for item in batch_result]

    async def _process_batch(self, batch: List[DocumentChunk]) -> List[EmbeddingResult]:
        start = time.perf_counter()
        async with self.semaphore:
            try:
                contents = [chunk.content for chunk in batch]
                embeddings = await self._call_openai_embeddings(contents)
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                results = []
                for chunk, embedding in zip(batch, embeddings):
                    results.append(self._build_result(chunk, embedding, "completed", None, elapsed_ms))
                return results
            except Exception as exc:
                self.logger.warning(
                    "Batch embedding failed, intentando por chunk individual",
                    extra={"batch_size": len(batch), "error": str(exc)},
                )

        results: List[EmbeddingResult] = []
        for chunk in batch:
            chunk_start = time.perf_counter()
            try:
                embedding = await self._call_openai_embeddings([chunk.content])
                elapsed_ms = int((time.perf_counter() - chunk_start) * 1000)
                results.append(self._build_result(chunk, embedding[0], "completed", None, elapsed_ms))
            except Exception as inner_exc:
                elapsed_ms = int((time.perf_counter() - chunk_start) * 1000)
                results.append(self._build_result(chunk, [], "failed", str(inner_exc), elapsed_ms))
        return results

    def _build_result(
        self,
        chunk: DocumentChunk,
        embedding: List[float],
        status: str,
        error: Optional[str],
        latency_ms: int,
    ) -> EmbeddingResult:
        metadata: Dict[str, Any] = {
            "embedding_model": self.model,
            "latency_ms": latency_ms,
            **chunk.metadata,
        }
        return EmbeddingResult(
            chunk_id=chunk.chunk_id,
            candidate_id=chunk.candidate_id,
            embedding=embedding,
            metadata=metadata,
            status=status,
            error=error,
        )

    @retry(
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _call_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        if AsyncOpenAI is None:
            raise RuntimeError("OpenAI library is not installed")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required")

        client = AsyncOpenAI(api_key=self.api_key)
        async with client as openai_client:
            response = await openai_client.embeddings.create(model=self.model, input=texts)

        if not response.data:
            raise RuntimeError("OpenAI embedding response malformed")

        embeddings: List[List[float]] = []
        for item in response.data:
            if not hasattr(item, "embedding"):
                raise RuntimeError("OpenAI embedding response malformed")
            embeddings.append(list(item.embedding))

        return embeddings

    def _batch_chunks(self, chunks: List[DocumentChunk]) -> List[List[DocumentChunk]]:
        return [chunks[i : i + self.batch_size] for i in range(0, len(chunks), self.batch_size)]
