# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .document_chunking import DocumentChunkingService
from .document_ingestion import DocumentIngestionService
from .embedding_service import EmbeddingService
from .models import DocumentIngestionResult, EmbeddingResult
from .vector_repository import ChromaVectorRepository

LOGGER = logging.getLogger("CVIndexingPipeline")

STATUS_COMPLETED = "completed"
STATUS_COMPLETED_WITH_ERRORS = "completed_with_errors"
STATUS_FAILED = "failed"


class CVIndexingRequest(BaseModel):
    cv_directory: str
    force_reindex: bool = False


class CVIndexingSummary(BaseModel):
    documents_found: int = 0
    documents_processed: int = 0
    documents_failed: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    chunks_stored: int = 0
    errors: List[str] = Field(default_factory=list)
    latency_ms: int = 0
    status: str = STATUS_COMPLETED


class CVIndexingPipeline:
    def __init__(
        self,
        ingestion_service: Optional[DocumentIngestionService] = None,
        chunking_service: Optional[DocumentChunkingService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        vector_repository: Optional[ChromaVectorRepository] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or LOGGER
        self.ingestion_service = ingestion_service or DocumentIngestionService()
        self.chunking_service = chunking_service or DocumentChunkingService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_repository = vector_repository or ChromaVectorRepository()

    async def index(self, request: CVIndexingRequest) -> CVIndexingSummary:
        start_time = time.perf_counter()
        errors: List[str] = []

        try:
            documents = await asyncio.to_thread(self.ingestion_service.ingest_directory, request.cv_directory)
        except Exception as exc:
            self.logger.error("Failed to ingest directory", exc_info=exc)
            return CVIndexingSummary(
                documents_found=0,
                documents_processed=0,
                documents_failed=0,
                chunks_created=0,
                embeddings_created=0,
                chunks_stored=0,
                errors=[f"Ingestion failed: {exc}"],
                latency_ms=int((time.perf_counter() - start_time) * 1000),
                status=STATUS_FAILED,
            )

        documents_found = len(documents)
        documents_processed = sum(1 for document in documents if document.status == "processed")
        documents_failed = documents_found - documents_processed
        failed_documents = [document for document in documents if document.status != "processed"]
        errors.extend(self._render_document_errors(failed_documents))

        valid_documents = [document for document in documents if document.status == "processed"]
        chunks = self.chunking_service.chunk_documents(valid_documents)
        chunks_created = len(chunks)

        embeddings: List[EmbeddingResult] = []
        try:
            embeddings = await self.embedding_service.generate_embeddings(chunks)
        except Exception as exc:
            self.logger.error("Embedding generation failed", exc_info=exc)
            errors.append(f"Embedding generation failed: {exc}")

        completed_embeddings = [embedding for embedding in embeddings if embedding.status == "completed"]
        embeddings_created = len(completed_embeddings)
        errors.extend(self._render_embedding_errors(embeddings))

        chunks_stored = 0
        try:
            chunks_stored = await asyncio.to_thread(
                self.vector_repository.upsert_chunks,
                chunks,
                completed_embeddings,
                request.force_reindex,
            )
        except Exception as exc:
            self.logger.error("Failed to store chunks in vector repository", exc_info=exc)
            errors.append(f"Vector repository storage failed: {exc}")

        status = STATUS_COMPLETED
        if errors:
            status = STATUS_COMPLETED_WITH_ERRORS if chunks_stored or embeddings_created else STATUS_FAILED

        return CVIndexingSummary(
            documents_found=documents_found,
            documents_processed=documents_processed,
            documents_failed=documents_failed,
            chunks_created=chunks_created,
            embeddings_created=embeddings_created,
            chunks_stored=chunks_stored,
            errors=errors,
            latency_ms=int((time.perf_counter() - start_time) * 1000),
            status=status,
        )

    def _render_document_errors(self, failed_documents: List[DocumentIngestionResult]) -> List[str]:
        errors: List[str] = []
        for document in failed_documents:
            if document.error:
                errors.append(f"{document.source_file}: {document.error}")
            else:
                errors.append(f"{document.source_file}: documento procesado con estado {document.status}")
        return errors

    def _render_embedding_errors(self, embeddings: List[EmbeddingResult]) -> List[str]:
        return [f"{embedding.chunk_id}: {embedding.error}" for embedding in embeddings if embedding.status != "completed" and embedding.error]
