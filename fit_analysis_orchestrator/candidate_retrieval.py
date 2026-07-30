# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, root_validator

from .models import CandidateSource

DEFAULT_CHUNKS_PER_QUERY = 5
DEFAULT_PAGE = 0
DEFAULT_SIMILARITY = 0.0


class CandidateChunk(BaseModel):
    content: str
    source_file: str
    page: int = DEFAULT_PAGE
    section: str = ""
    chunk_id: str
    similarity_score: float
    query_group: str


class CandidateRetrievalResult(BaseModel):
    candidate_id: str
    retrieval_score: float
    matched_query_groups: List[str] = Field(default_factory=list)
    matched_requirements: List[str] = Field(default_factory=list)
    relevant_chunks: List[CandidateChunk] = Field(default_factory=list)


class CandidateRetrievalMetrics(BaseModel):
    queries_executed: int
    chunks_retrieved: int
    candidates_found: int
    elapsed_ms: int
    average_score: float
    knowledge_gaps: List[str] = Field(default_factory=list)


class CandidateRetrievalWorker:
    """Worker that performs semantic retrieval over candidate CV fragments."""

    def __init__(self, vector_store: Any = None) -> None:
        self.vector_store = vector_store
        self.chunks_per_query = self._configure_chunks_per_query()

    def _configure_chunks_per_query(self) -> int:
        raw_value = os.getenv("CANDIDATE_RETRIEVAL_CHUNKS_PER_QUERY")
        if raw_value is None:
            return DEFAULT_CHUNKS_PER_QUERY
        try:
            result = int(raw_value)
            return max(1, result)
        except ValueError:
            return DEFAULT_CHUNKS_PER_QUERY

    async def execute(self, cv_directory: str, max_candidates: int) -> Tuple[List[CandidateSource], int]:
        start = time.perf_counter()
        await asyncio.sleep(0)

        path = os.fspath(cv_directory)
        if not os.path.isdir(path):
            raise ValueError(f"El directorio de CV no existe: {cv_directory}")

        candidates: List[CandidateSource] = []
        for file_name in sorted(os.listdir(path)):
            candidate_path = os.path.join(path, file_name)
            if not os.path.isfile(candidate_path):
                continue
            _, ext = os.path.splitext(candidate_path)
            if ext.lower() not in {".txt", ".md", ".pdf", ".docx"}:
                continue
            candidates.append(
                CandidateSource(
                    candidate_id=os.path.splitext(file_name)[0],
                    source_path=candidate_path,
                    name=os.path.splitext(file_name)[0].replace("_", " "),
                )
            )
            if len(candidates) >= max_candidates:
                break

        if not candidates:
            raise ValueError("No se encontraron CV válidos en el directorio de candidatos.")

        elapsed = int((time.perf_counter() - start) * 1000)
        tokens = 5 + len(candidates)
        return candidates, tokens

    async def search(
        self,
        job_description: Dict[str, Any],
        top_k_candidates: int = 10,
        chunks_per_query: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[CandidateRetrievalResult], CandidateRetrievalMetrics, int]:
        if self.vector_store is None:
            raise ValueError("No vector store configurado para búsqueda semántica.")

        start = time.perf_counter()
        await asyncio.sleep(0)

        chunks_per_query = chunks_per_query or self.chunks_per_query
        query_groups = self._build_query_groups(job_description)
        if not query_groups:
            raise ValueError("El descriptivo de rol no contiene datos suficientes para construir consultas semánticas.")

        raw_hits: List[Dict[str, Any]] = []
        for group_name, query_text in query_groups.items():
            if not query_text:
                continue
            hits = await self._query_vector_store(query_text, chunks_per_query, filters)
            for hit in hits:
                hit["query_group"] = group_name
                raw_hits.append(hit)

        grouped = self._group_chunks_by_candidate(raw_hits)
        results = self._build_results(grouped, top_k_candidates)
        metrics = self._build_metrics(query_groups, results, start)
        tokens = 15 + len(results) * 2
        return results, metrics, tokens

    async def _query_vector_store(self, query: str, k: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = self.vector_store.query(query=query, k=k, filters=filters)
        if asyncio.iscoroutine(result):
            result = await result
        return result or []

    def _build_query_groups(self, job_description: Dict[str, Any]) -> Dict[str, str]:
        raw_title = self._text_value(job_description.get("role_title"))
        raw_summary = self._text_value(job_description.get("role_summary") or job_description.get("description_text"))
        raw_responsibilities = self._list_value(job_description.get("responsibilities"))
        raw_technologies = self._list_value(job_description.get("technologies"))
        raw_certifications = self._list_value(job_description.get("certifications"))

        mandatory_requirements = []
        desirable_requirements = []
        requirements = job_description.get("requirements") or []
        for req in requirements:
            name = self._requirement_name(req)
            if not name:
                continue
            if self._is_mandatory(req):
                mandatory_requirements.append(name)
            else:
                desirable_requirements.append(name)

        query_groups: Dict[str, str] = {
            "role_title": raw_title,
            "mandatory_requirements": " ".join(mandatory_requirements) if mandatory_requirements else raw_summary,
            "technologies": " ".join(raw_technologies),
            "responsibilities": " ".join(raw_responsibilities),
            "experience": self._extract_experience_text(job_description),
            "certifications": " ".join(raw_certifications),
            "desirable_requirements": " ".join(desirable_requirements),
        }

        return {name: text for name, text in query_groups.items() if text}

    def _text_value(self, value: Any) -> str:
        if not value:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return " ".join(str(item).strip() for item in value if item)
        return str(value).strip()

    def _list_value(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if item]
        return [str(value).strip()]

    def _requirement_name(self, requirement: Any) -> str:
        if isinstance(requirement, str):
            return requirement.strip()
        if isinstance(requirement, dict):
            return self._text_value(requirement.get("name") or requirement.get("source_text"))
        return ""

    def _is_mandatory(self, requirement: Any) -> bool:
        if isinstance(requirement, dict):
            return bool(requirement.get("mandatory"))
        return False

    def _extract_experience_text(self, job_description: Dict[str, Any]) -> str:
        text = self._text_value(job_description.get("role_summary"))
        if not text:
            text = self._text_value(job_description.get("description_text"))
        match = re.search(r"(\d+\s*(?:años|years|yrs|anos))", text, re.IGNORECASE)
        return match.group(0) if match else text

    def _group_chunks_by_candidate(self, hits: List[Dict[str, Any]]) -> Dict[str, List[CandidateChunk]]:
        grouped: Dict[str, List[CandidateChunk]] = {}
        for hit in hits:
            candidate_id = str(hit.get("candidate_id", "")).strip()
            if not candidate_id:
                continue
            chunk = CandidateChunk(
                content=self._text_value(hit.get("content")),
                source_file=self._text_value(hit.get("source_file")) or self._candidate_source(hit),
                page=int(hit.get("page", DEFAULT_PAGE) or DEFAULT_PAGE),
                section=self._text_value(hit.get("section")),
                chunk_id=str(hit.get("chunk_id") or hit.get("id") or f"{candidate_id}-{len(grouped.get(candidate_id, []))}"),
                similarity_score=float(hit.get("similarity_score", DEFAULT_SIMILARITY) or DEFAULT_SIMILARITY),
                query_group=self._text_value(hit.get("query_group")),
            )
            grouped.setdefault(candidate_id, []).append(chunk)

        for candidate_id, chunks in grouped.items():
            grouped[candidate_id] = self._deduplicate_chunks(chunks)
        return grouped

    def _candidate_source(self, hit: Dict[str, Any]) -> str:
        source = hit.get("source_file") or hit.get("source") or hit.get("candidate_id")
        return str(source or "")

    def _deduplicate_chunks(self, chunks: List[CandidateChunk]) -> List[CandidateChunk]:
        unique: Dict[str, CandidateChunk] = {}
        for chunk in chunks:
            if chunk.chunk_id not in unique:
                unique[chunk.chunk_id] = chunk
        return list(unique.values())

    def _compute_candidate_score(self, chunks: List[CandidateChunk]) -> float:
        if not chunks:
            return 0.0
        group_best: Dict[str, float] = {}
        for chunk in chunks:
            group_best[chunk.query_group] = max(group_best.get(chunk.query_group, 0.0), chunk.similarity_score)
        return sum(group_best.values()) / len(group_best)

    def _build_results(self, grouped: Dict[str, List[CandidateChunk]], top_k_candidates: int) -> List[CandidateRetrievalResult]:
        candidate_scores = {
            candidate_id: self._compute_candidate_score(chunks)
            for candidate_id, chunks in grouped.items()
        }
        if not candidate_scores:
            return []

        max_score = max(candidate_scores.values())
        normalized_scores = {
            cid: (score / max_score if max_score > 0 else 0.0)
            for cid, score in candidate_scores.items()
        }

        results = []
        for candidate_id, chunks in grouped.items():
            groups = sorted({chunk.query_group for chunk in chunks})
            matched_requirements = sorted({self._extract_requirement_from_chunk(chunk) for chunk in chunks if self._extract_requirement_from_chunk(chunk)})
            results.append(
                CandidateRetrievalResult(
                    candidate_id=candidate_id,
                    retrieval_score=round(normalized_scores[candidate_id], 4),
                    matched_query_groups=groups,
                    matched_requirements=matched_requirements,
                    relevant_chunks=chunks,
                )
            )

        results.sort(key=lambda item: item.retrieval_score, reverse=True)
        return results[:top_k_candidates]

    def _extract_requirement_from_chunk(self, chunk: CandidateChunk) -> str:
        if "requirement" in chunk.section.lower():
            return chunk.section
        return ""

    def _build_metrics(
        self,
        query_groups: Dict[str, str],
        results: List[CandidateRetrievalResult],
        start_time: float,
    ) -> CandidateRetrievalMetrics:
        elapsed = int((time.perf_counter() - start_time) * 1000)
        total_chunks = sum(len(result.relevant_chunks) for result in results)
        average_score = round(sum(result.retrieval_score for result in results) / len(results), 4) if results else 0.0
        knowledge_gaps: List[str] = []
        if len(results) < len(query_groups):
            knowledge_gaps.append(
                "No se encontraron suficientes candidatos para cubrir todas las consultas semánticas."
            )
        if not results:
            knowledge_gaps.append("No se encontraron candidatos relevantes en la búsqueda vectorial.")
        return CandidateRetrievalMetrics(
            queries_executed=len(query_groups),
            chunks_retrieved=total_chunks,
            candidates_found=len(results),
            elapsed_ms=elapsed,
            average_score=average_score,
            knowledge_gaps=knowledge_gaps,
        )


class MockVectorStore(BaseModel):
    responses: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)

    @root_validator(pre=True)
    def normalize_keys(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        raw = values.get("responses", {})
        values["responses"] = {
            str(key).strip().lower(): list(items)
            for key, items in raw.items()
        }
        return values

    async def query(self, query: str, k: int, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        normalized = query.strip().lower()
        if normalized in self.responses:
            return self.responses[normalized][:k]

        for key, items in self.responses.items():
            if key in normalized or normalized in key:
                return items[:k]
        return []
