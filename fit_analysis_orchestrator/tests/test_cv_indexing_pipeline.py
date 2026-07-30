# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fit_analysis_orchestrator.cv_indexing_pipeline import (
    CVIndexingPipeline,
    CVIndexingRequest,
)
from fit_analysis_orchestrator.models import DocumentChunk, DocumentIngestionResult, EmbeddingResult


def test_cv_indexing_pipeline_index_success():
    ingestion_service = MagicMock()
    chunking_service = MagicMock()
    embedding_service = MagicMock()
    vector_repository = MagicMock()

    ingestion_service.ingest_directory.return_value = [
        DocumentIngestionResult(
            candidate_id="c1",
            source_file="/tmp/c1.txt",
            file_type="txt",
            content="Experiencia en Python.",
            page_count=0,
            document_hash="hash1",
            metadata={},
            status="processed",
            error=None,
        ),
        DocumentIngestionResult(
            candidate_id="c2",
            source_file="/tmp/c2.txt",
            file_type="txt",
            content="Experiencia en SQL.",
            page_count=0,
            document_hash="hash2",
            metadata={},
            status="failed",
            error="corrupt file",
        ),
    ]

    chunk = DocumentChunk(
        chunk_id="chunk-1",
        candidate_id="c1",
        content="Experiencia en Python.",
        source_file="/tmp/c1.txt",
        page=None,
        section=None,
        chunk_index=0,
        metadata={},
    )
    chunking_service.chunk_documents.return_value = [chunk]

    embedding = EmbeddingResult(
        chunk_id="chunk-1",
        candidate_id="c1",
        embedding=[0.1, 0.2, 0.3],
        metadata={"embedding_model": "text-embedding-3-large"},
        status="completed",
        error=None,
    )
    embedding_service.generate_embeddings = AsyncMock(return_value=[embedding])
    vector_repository.upsert_chunks.return_value = 1

    pipeline = CVIndexingPipeline(
        ingestion_service=ingestion_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        vector_repository=vector_repository,
    )

    request = CVIndexingRequest(cv_directory=str(Path("/tmp/cvs")), force_reindex=True)
    summary = asyncio.run(pipeline.index(request))

    assert summary.documents_found == 2
    assert summary.documents_processed == 1
    assert summary.documents_failed == 1
    assert summary.chunks_created == 1
    assert summary.embeddings_created == 1
    assert summary.chunks_stored == 1
    assert summary.status == "completed_with_errors"
    assert any("corrupt file" in error for error in summary.errors)


def test_cv_indexing_pipeline_index_continues_on_embedding_failure():
    ingestion_service = MagicMock()
    chunking_service = MagicMock()
    embedding_service = MagicMock()
    vector_repository = MagicMock()

    ingestion_service.ingest_directory.return_value = [
        DocumentIngestionResult(
            candidate_id="c1",
            source_file="/tmp/c1.txt",
            file_type="txt",
            content="Experiencia en Python.",
            page_count=0,
            document_hash="hash1",
            metadata={},
            status="processed",
            error=None,
        )
    ]

    chunk = DocumentChunk(
        chunk_id="chunk-1",
        candidate_id="c1",
        content="Experiencia en Python.",
        source_file="/tmp/c1.txt",
        page=None,
        section=None,
        chunk_index=0,
        metadata={},
    )
    chunking_service.chunk_documents.return_value = [chunk]

    embedding_service.generate_embeddings = AsyncMock(return_value=[
        EmbeddingResult(
            chunk_id="chunk-1",
            candidate_id="c1",
            embedding=[],
            metadata={},
            status="failed",
            error="timeout",
        )
    ])
    vector_repository.upsert_chunks.return_value = 0

    pipeline = CVIndexingPipeline(
        ingestion_service=ingestion_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        vector_repository=vector_repository,
    )

    request = CVIndexingRequest(cv_directory=str(Path("/tmp/cvs")), force_reindex=False)
    summary = asyncio.run(pipeline.index(request))

    assert summary.documents_found == 1
    assert summary.documents_processed == 1
    assert summary.documents_failed == 0
    assert summary.chunks_created == 1
    assert summary.embeddings_created == 0
    assert summary.chunks_stored == 0
    assert summary.status == "failed"
    assert "timeout" in summary.errors[0]
