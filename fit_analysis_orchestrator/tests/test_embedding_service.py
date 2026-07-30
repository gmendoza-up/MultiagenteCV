# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

from fit_analysis_orchestrator.embedding_service import EmbeddingService
from fit_analysis_orchestrator.models import DocumentChunk


class DummyResponseItem:
    def __init__(self, embedding: list[float]):
        self.embedding = embedding


class DummyResponse:
    def __init__(self, data: list[DummyResponseItem]):
        self.data = data


@patch("fit_analysis_orchestrator.embedding_service.AsyncOpenAI")
def test_generate_embeddings_success(mock_openai):
    os.environ["OPENAI_API_KEY"] = "test_key"
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.embeddings.create = AsyncMock(
        return_value=DummyResponse([DummyResponseItem([0.1, 0.2, 0.3])])
    )
    mock_openai.return_value = mock_client

    chunks = [
        DocumentChunk(
            chunk_id="c1",
            candidate_id="candidate_1",
            content="test content",
            source_file="c1.txt",
            page=None,
            section=None,
            chunk_index=0,
            metadata={},
        )
    ]

    service = EmbeddingService(batch_size=1, concurrency=1)
    results = asyncio.run(service.generate_embeddings(chunks))

    assert len(results) == 1
    assert results[0].chunk_id == "c1"
    assert results[0].status == "completed"
    assert results[0].embedding == [0.1, 0.2, 0.3]
    assert results[0].error is None


@patch("fit_analysis_orchestrator.embedding_service.AsyncOpenAI")
def test_generate_embeddings_chunk_failure_continues(mock_openai):
    os.environ["OPENAI_API_KEY"] = "test_key"
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.embeddings.create = AsyncMock(
        side_effect=[
            Exception("rate limit"),
            DummyResponse([DummyResponseItem([0.4, 0.5, 0.6])]),
        ]
    )
    mock_openai.return_value = mock_client

    chunks = [
        DocumentChunk(
            chunk_id="c1",
            candidate_id="candidate_1",
            content="valid content",
            source_file="c1.txt",
            page=None,
            section=None,
            chunk_index=0,
            metadata={},
        )
    ]

    service = EmbeddingService(batch_size=1, concurrency=1)
    results = asyncio.run(service.generate_embeddings(chunks))

    assert len(results) == 1
    assert results[0].status == "completed"
    assert results[0].embedding == [0.4, 0.5, 0.6]
