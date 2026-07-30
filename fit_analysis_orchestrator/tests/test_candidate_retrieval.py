# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fit_analysis_orchestrator.candidate_retrieval import (
    CandidateRetrievalWorker,
    MockVectorStore,
)


def test_candidate_retrieval_search_groups_and_scores():
    store = MockVectorStore(
        responses={
            "data engineer": [
                {
                    "candidate_id": "c1",
                    "content": "Experiencia en Python y AWS.",
                    "source_file": "c1.txt",
                    "page": 1,
                    "section": "Technology",
                    "chunk_id": "c1-1",
                    "similarity_score": 0.9,
                },
                {
                    "candidate_id": "c2",
                    "content": "Proyecto de ETL con Python.",
                    "source_file": "c2.txt",
                    "page": 2,
                    "section": "Experience",
                    "chunk_id": "c2-1",
                    "similarity_score": 0.85,
                },
            ],
            "python sql aws": [
                {
                    "candidate_id": "c1",
                    "content": "Python, SQL y AWS en producción.",
                    "source_file": "c1.txt",
                    "page": 1,
                    "section": "Technology",
                    "chunk_id": "c1-2",
                    "similarity_score": 0.8,
                }
            ],
        }
    )
    worker = CandidateRetrievalWorker(vector_store=store)
    payload = {
        "role_title": "Data Engineer",
        "role_summary": "Ingeniero de datos con experiencia en Python, SQL y AWS.",
        "requirements": [
            {"name": "Python", "mandatory": True},
            {"name": "SQL", "mandatory": True},
            {"name": "AWS", "mandatory": False},
        ],
        "technologies": ["Python", "SQL", "AWS"],
        "responsibilities": ["Construir pipelines de datos."],
        "certifications": ["AWS Certified Data Analytics"],
    }

    results, metrics, tokens = asyncio.run(worker.search(payload, top_k_candidates=2))

    assert tokens > 0
    assert metrics.queries_executed >= 1
    assert metrics.candidates_found == 2
    assert len(results) == 2
    assert results[0].candidate_id == "c1"
    assert results[0].retrieval_score >= results[1].retrieval_score
    assert any(chunk.source_file == "c1.txt" for chunk in results[0].relevant_chunks)


def test_candidate_retrieval_returns_all_candidates_if_less_than_top_k():
    store = MockVectorStore(responses={"data engineer": []})
    worker = CandidateRetrievalWorker(vector_store=store)
    payload = {
        "role_title": "Data Engineer",
        "role_summary": "Rol con poco contenido.",
        "requirements": [],
        "technologies": [],
        "responsibilities": [],
        "certifications": [],
    }

    results, metrics, tokens = asyncio.run(worker.search(payload, top_k_candidates=10))

    assert results == []
    assert metrics.candidates_found == 0
    assert "No se encontraron candidatos relevantes en la búsqueda vectorial." in metrics.knowledge_gaps


def test_candidate_retrieval_deduplicates_chunks_by_id():
    store = MockVectorStore(
        responses={
            "data engineer": [
                {
                    "candidate_id": "c1",
                    "content": "Python.",
                    "source_file": "c1.txt",
                    "page": 1,
                    "section": "Technology",
                    "chunk_id": "dup",
                    "similarity_score": 0.7,
                },
                {
                    "candidate_id": "c1",
                    "content": "Python repeated.",
                    "source_file": "c1.txt",
                    "page": 1,
                    "section": "Technology",
                    "chunk_id": "dup",
                    "similarity_score": 0.75,
                },
            ]
        }
    )
    worker = CandidateRetrievalWorker(vector_store=store)
    payload = {
        "role_title": "Data Engineer",
        "role_summary": "Experiencia en Python.",
        "requirements": [],
        "technologies": ["Python"],
        "responsibilities": [],
        "certifications": [],
    }

    results, metrics, tokens = asyncio.run(worker.search(payload, top_k_candidates=1))
    assert len(results) == 1
    assert len(results[0].relevant_chunks) == 1


def test_candidate_retrieval_preserves_metadata_and_source():
    store = MockVectorStore(
        responses={
            "data engineer": [
                {
                    "candidate_id": "c3",
                    "content": "Experiencia con AWS y Python.",
                    "source_file": "perfil/c3_cv.txt",
                    "page": 3,
                    "section": "Experiencia",
                    "chunk_id": "c3-1",
                    "similarity_score": 0.92,
                }
            ]
        }
    )
    worker = CandidateRetrievalWorker(vector_store=store)
    payload = {
        "role_title": "Data Engineer",
        "role_summary": "Rol con experiencia en AWS y Python.",
        "requirements": [],
        "technologies": ["AWS", "Python"],
        "responsibilities": [],
        "certifications": [],
    }

    results, metrics, tokens = asyncio.run(worker.search(payload, top_k_candidates=1))
    assert results[0].candidate_id == "c3"
    chunk = results[0].relevant_chunks[0]
    assert chunk.source_file == "perfil/c3_cv.txt"
    assert chunk.page == 3
    assert chunk.section == "Experiencia"
    assert chunk.chunk_id == "c3-1"
    assert chunk.similarity_score == 0.92
