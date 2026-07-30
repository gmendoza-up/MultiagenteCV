# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

from .models import DocumentChunk, DocumentIngestionResult

LOGGER = logging.getLogger("DocumentChunkingService")

DEFAULT_CHUNK_SIZE = 200
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_MINIMUM_CHUNK_RATIO = 0.5


class DocumentChunkingService:
    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or LOGGER
        self.chunk_size = int(
            os.getenv("DOCUMENT_CHUNK_SIZE", str(chunk_size or DEFAULT_CHUNK_SIZE))
        )
        self.chunk_overlap = int(
            os.getenv("DOCUMENT_CHUNK_OVERLAP", str(chunk_overlap or DEFAULT_CHUNK_OVERLAP))
        )
        self.chunk_size = max(1, self.chunk_size)
        self.chunk_overlap = min(max(0, self.chunk_overlap), self.chunk_size - 1)
        self.minimum_chunk_size = max(1, int(self.chunk_size * DEFAULT_MINIMUM_CHUNK_RATIO))

    def chunk_documents(
        self, documents: List[DocumentIngestionResult]
    ) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []

        for document in documents:
            document_chunks = self._chunk_document(document)
            chunks.extend(document_chunks)

        return chunks

    def _chunk_document(self, document: DocumentIngestionResult) -> List[DocumentChunk]:
        content = (document.content or "").strip()
        if not content:
            self.logger.warning(
                "Documento sin contenido omitido",
                extra={"source_file": document.source_file},
            )
            return []

        words = content.split()
        if not words:
            return []

        chunks: List[DocumentChunk] = []
        start = 0
        chunk_index = 0

        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words).strip()
            if chunk_text:
                chunk_id = self._build_chunk_id(document, chunk_index, chunk_text)
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    candidate_id=document.candidate_id,
                    content=chunk_text,
                    source_file=document.source_file,
                    page=self._extract_page(document),
                    section=self._extract_section(document),
                    chunk_index=chunk_index,
                    metadata={**document.metadata, "original_page_count": document.page_count},
                )
                chunks.append(chunk)
                chunk_index += 1

            if end == len(words):
                break

            start += self.chunk_size - self.chunk_overlap

        if len(chunks) > 1 and len(chunks[-1].content.split()) < self.minimum_chunk_size:
            last_chunk = chunks.pop()
            previous_chunk = chunks.pop()
            merged_text = f"{previous_chunk.content} {last_chunk.content}".strip()
            merged_chunk = DocumentChunk(
                chunk_id=self._build_chunk_id(document, previous_chunk.chunk_index, merged_text),
                candidate_id=document.candidate_id,
                content=merged_text,
                source_file=document.source_file,
                page=previous_chunk.page,
                section=previous_chunk.section,
                chunk_index=previous_chunk.chunk_index,
                metadata={**previous_chunk.metadata, "merged": True},
            )
            chunks.append(merged_chunk)

        return chunks

    def _build_chunk_id(
        self, document: DocumentIngestionResult, chunk_index: int, content: str
    ) -> str:
        fingerprint = f"{document.candidate_id}|{document.source_file}|{chunk_index}|{content}"
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _extract_page(self, document: DocumentIngestionResult) -> Optional[int]:
        page_value = document.metadata.get("page")
        try:
            return int(page_value) if page_value is not None else None
        except (ValueError, TypeError):
            return None

    def _extract_section(self, document: DocumentIngestionResult) -> Optional[str]:
        section_value = document.metadata.get("section")
        return str(section_value) if section_value is not None else None
