# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import DocumentIngestionResult

LOGGER = logging.getLogger("DocumentIngestionService")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class UnsupportedFileTypeError(Exception):
    pass


class DocumentIngestionService:
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or LOGGER

    def ingest_directory(self, directory: str) -> List[DocumentIngestionResult]:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"El directorio no existe o no es un directorio: {directory}")

        results: List[DocumentIngestionResult] = []
        seen_hashes: set[str] = set()
        for file_path in sorted(path.iterdir()):
            if not file_path.is_file():
                continue
            result = self._process_file(file_path, seen_hashes)
            results.append(result)
        return results

    def _process_file(
        self, file_path: Path, seen_hashes: set[str]
    ) -> DocumentIngestionResult:
        candidate_id = file_path.stem
        file_type = file_path.suffix.lower().lstrip(".")
        document_hash = self._hash_file(file_path)

        if document_hash in seen_hashes:
            message = "duplicate document"
            self.logger.warning(
                "Documento duplicado ignorado",
                extra={"source_file": str(file_path), "document_hash": document_hash},
            )
            return DocumentIngestionResult(
                candidate_id=candidate_id,
                source_file=str(file_path),
                file_type=file_type,
                content="",
                page_count=0,
                document_hash=document_hash,
                metadata={},
                status="failed",
                error=message,
            )

        seen_hashes.add(document_hash)
        content = ""
        page_count = 0
        metadata: Dict[str, Any] = {}
        status = "processed"
        error: Optional[str] = None

        try:
            if file_path.suffix.lower() == ".pdf":
                content, page_count, metadata = self._read_pdf(file_path)
            elif file_path.suffix.lower() == ".docx":
                content, page_count, metadata = self._read_docx(file_path)
            elif file_path.suffix.lower() == ".txt":
                content, page_count, metadata = self._read_txt(file_path)
            else:
                raise UnsupportedFileTypeError(
                    f"Extensión no soportada: {file_path.suffix}"
                )
        except Exception as exc:
            self.logger.error(
                "Error procesando archivo %s: %s", file_path, exc, extra={"source_file": str(file_path)}
            )
            status = "failed"
            error = str(exc)
            content = ""
            page_count = 0
            metadata = {}

        return DocumentIngestionResult(
            candidate_id=candidate_id,
            source_file=str(file_path),
            file_type=file_type,
            content=content,
            page_count=page_count,
            document_hash=document_hash,
            metadata=metadata,
            status=status,
            error=error,
        )

    def _hash_file(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _read_pdf(self, file_path: Path) -> tuple[str, int, Dict[str, Any]]:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages: List[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")

        metadata: Dict[str, Any] = {}
        if reader.metadata:
            for key, value in reader.metadata.items():
                if value is not None:
                    normalized_key = str(key).lstrip("/")
                    metadata[normalized_key] = value

        return "\n".join(pages), len(reader.pages), metadata

    def _read_docx(self, file_path: Path) -> tuple[str, int, Dict[str, Any]]:
        from docx import Document

        document = Document(str(file_path))
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        metadata = self._document_core_properties(document)
        return "\n".join(paragraphs), 0, metadata

    def _read_txt(self, file_path: Path) -> tuple[str, int, Dict[str, Any]]:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return text, 0, {}

    def _document_core_properties(self, document: Any) -> Dict[str, Any]:
        props = document.core_properties
        metadata: Dict[str, Any] = {}
        for field_name in [
            "author",
            "category",
            "comments",
            "content_status",
            "created",
            "identifier",
            "keywords",
            "language",
            "last_modified_by",
            "modified",
            "revision",
            "subject",
            "title",
            "version",
        ]:
            value = getattr(props, field_name, None)
            if value is not None:
                metadata[field_name] = str(value)
        return metadata
