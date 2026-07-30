# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from fit_analysis_orchestrator.document_chunking import DocumentChunkingService
from fit_analysis_orchestrator.models import DocumentIngestionResult


def test_chunk_documents_respects_chunk_size_and_overlap():
    document = DocumentIngestionResult(
        candidate_id="c1",
        source_file="c1.txt",
        file_type="txt",
        content="".join([f"palabra{i} " for i in range(60)]).strip(),
        page_count=0,
        document_hash="hash1",
        metadata={"section": "Resumen"},
        status="processed",
    )

    service = DocumentChunkingService(chunk_size=20, chunk_overlap=5)
    chunks = service.chunk_documents([document])

    assert len(chunks) == 4
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2
    assert chunks[3].chunk_index == 3
    assert chunks[0].content.split()[0] == "palabra0"
    assert chunks[1].content.split()[0] == "palabra15"
    assert chunks[2].content.split()[0] == "palabra30"
    assert chunks[3].content.split()[0] == "palabra45"
    assert chunks[0].section == "Resumen"
    assert chunks[0].source_file == "c1.txt"


def test_chunk_documents_avoids_empty_and_short_chunks():
    short_text = "a " * 15
    document = DocumentIngestionResult(
        candidate_id="c2",
        source_file="c2.txt",
        file_type="txt",
        content=short_text.strip(),
        page_count=0,
        document_hash="hash2",
        metadata={"section": "Experiencia"},
        status="processed",
    )

    service = DocumentChunkingService(chunk_size=20, chunk_overlap=5)
    chunks = service.chunk_documents([document])

    assert len(chunks) == 1
    assert chunks[0].content == short_text.strip()
    assert chunks[0].chunk_index == 0


def test_chunk_documents_preserves_candidate_and_source_metadata():
    document = DocumentIngestionResult(
        candidate_id="c3",
        source_file="c3.docx",
        file_type="docx",
        content="Este es un texto de prueba con varias palabras para dividir.",
        page_count=0,
        document_hash="hash3",
        metadata={"section": "Formación", "page": 2},
        status="processed",
    )

    service = DocumentChunkingService(chunk_size=12, chunk_overlap=3)
    chunks = service.chunk_documents([document])

    assert len(chunks) == 1
    assert chunks[0].candidate_id == "c3"
    assert chunks[0].source_file == "c3.docx"
    assert chunks[0].page == 2
    assert chunks[0].section == "Formación"
    assert chunks[0].chunk_id


def test_chunk_documents_ignores_empty_content():
    document = DocumentIngestionResult(
        candidate_id="c4",
        source_file="c4.txt",
        file_type="txt",
        content="   ",
        page_count=0,
        document_hash="hash4",
        metadata={},
        status="processed",
    )

    service = DocumentChunkingService(chunk_size=10, chunk_overlap=2)
    chunks = service.chunk_documents([document])

    assert chunks == []


def test_chunking_chunk_id_is_unique():
    document = DocumentIngestionResult(
        candidate_id="c5",
        source_file="c5.txt",
        file_type="txt",
        content="uno dos tres cuatro cinco seis siete ocho nueve diez.",
        page_count=0,
        document_hash="hash5",
        metadata={},
        status="processed",
    )

    service = DocumentChunkingService(chunk_size=5, chunk_overlap=1)
    chunks = service.chunk_documents([document])

    ids = {chunk.chunk_id for chunk in chunks}
    assert len(ids) == len(chunks)
