# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fit_analysis_orchestrator.supervisor_agent import SupervisorAgent


def build_fit(candidate_id: str, fit_percentage: float, mandatory_fit: float, confidence: float, request_assessments=None, exclusionary_flags=None, retrieval_score=0.0):
    if request_assessments is None:
        request_assessments = []
    if exclusionary_flags is None:
        exclusionary_flags = []
    return {
        "candidate_id": candidate_id,
        "fit_percentage": fit_percentage,
        "mandatory_fit": mandatory_fit,
        "confidence": confidence,
        "requirement_assessments": request_assessments,
        "exclusionary_flags": exclusionary_flags,
        "retrieval_score": retrieval_score,
    }


def test_supervisor_approves_when_quality_is_high():
    agent = SupervisorAgent()
    payload = {
        "job_description": {"description_text": "Analista de datos con experiencia en Python."},
        "candidate_profiles": [{"candidate_id": "c1", "interview_questions": [{"question": "q1"}] * 5}],
        "fit_results": [build_fit("c1", 82.0, 55.0, 0.8, request_assessments=[{"mandatory": True, "status": "met", "evidence": ["x"]}])],
        "ranking_result": {"ranking": [{"candidate_id": "c1"}], "total_candidates": 1},
        "traces": [],
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result.status in {"approved", "modified_and_approved"}
    assert result.approved is True
    assert result.quality_score >= 0.6
    assert result.modifications is not None


def test_supervisor_approves_when_warning_present():
    agent = SupervisorAgent()
    payload = {
        "job_description": {"description_text": "Analista de datos con experiencia en Python."},
        "candidate_profiles": [{"candidate_id": "c1", "interview_questions": [{"question": "q1"}] * 5}],
        "fit_results": [build_fit("c1", 82.0, 55.0, 0.8, request_assessments=[{"mandatory": True, "status": "met", "evidence": ["x"]}])],
        "ranking_result": {"ranking": [{"candidate_id": "c1"}], "total_candidates": 1, "methodological_warning": "El ranking es una herramienta de apoyo a la decisión y no reemplaza la evaluación profesional ni la entrevista."},
        "traces": [],
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result.status == "approved"
    assert result.approved is True
    assert result.modifications is None


def test_supervisor_rejects_sensitive_data():
    agent = SupervisorAgent()
    payload = {
        "job_description": {"description_text": "Analista de datos."},
        "candidate_profiles": [{"candidate_id": "c1", "interview_questions": [{"question": "q1"}] * 5, "summary": "Edad 30"}],
        "fit_results": [build_fit("c1", 72.0, 45.0, 0.7, request_assessments=[{"mandatory": True, "status": "met", "evidence": ["x"]}])],
        "ranking_result": {"ranking": [{"candidate_id": "c1"}], "total_candidates": 1},
        "traces": [],
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result.status == "rejected"
    assert result.approved is False
    assert "sensitive_data" in result.flags


def test_supervisor_rejects_low_quality():
    agent = SupervisorAgent()
    payload = {
        "job_description": {"description_text": "Analista de datos."},
        "candidate_profiles": [{"candidate_id": "c1", "interview_questions": [{"question": "q1"}] * 3}],
        "fit_results": [build_fit("c1", 72.0, 45.0, 0.7, request_assessments=[{"mandatory": True, "status": "met", "evidence": ["x"]}])],
        "ranking_result": {"ranking": [{"candidate_id": "c1"}], "total_candidates": 1},
        "traces": [],
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result.status == "rejected"
    assert result.approved is False
    assert any("calidad" in issue.lower() for issue in result.issues)


def test_supervisor_handles_ranking_inconsistency():
    agent = SupervisorAgent()
    payload = {
        "job_description": {"description_text": "Analista de datos."},
        "candidate_profiles": [
            {"candidate_id": "c1", "interview_questions": [{"question": "q1"}] * 5},
            {"candidate_id": "c2", "interview_questions": [{"question": "q1"}] * 5},
        ],
        "fit_results": [
            build_fit("c1", 85.0, 55.0, 0.8, request_assessments=[{"mandatory": True, "status": "met", "evidence": ["x"]}]),
            build_fit("c2", 80.0, 50.0, 0.9, request_assessments=[{"mandatory": True, "status": "met", "evidence": ["x"]}]),
        ],
        "ranking_result": {"ranking": [{"candidate_id": "c2"}, {"candidate_id": "c1"}], "total_candidates": 2},
        "traces": [],
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result.status in {"approved", "modified_and_approved"}
    assert result.modifications is not None
    assert result.final_result["ranking"][0]["candidate_id"] == "c1"


def test_supervisor_rejects_missing_analysis():
    agent = SupervisorAgent()
    payload = {
        "job_description": {"description_text": "Analista de datos."},
        "candidate_profiles": [],
        "fit_results": [],
        "ranking_result": {"ranking": [], "total_candidates": 0},
        "traces": [],
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result.status == "rejected"
    assert any("faltan perfiles" in issue.lower() for issue in result.issues)
