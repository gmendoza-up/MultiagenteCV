# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fit_analysis_orchestrator.models import CandidateResult, FitAssessment, RequirementAssessment, InterviewQuestion
from fit_analysis_orchestrator.ranking_agent import RankingAgent


def build_candidate(candidate_id: str, fit_percentage: float, mandatory_fit: float, confidence: float, exclusionary_flags=None, requirement_assessments=None, retrieval_score=0.0):
    if exclusionary_flags is None:
        exclusionary_flags = []
    if requirement_assessments is None:
        requirement_assessments = []
    fit_assessment = FitAssessment(
        candidate_id=candidate_id,
        fit_percentage=fit_percentage,
        fit_level="high" if fit_percentage >= 75 else "medium" if fit_percentage >= 45 else "low",
        mandatory_fit=mandatory_fit,
        desirable_fit=100.0 - mandatory_fit,
        strengths=["Strength"],
        gaps=["Gap"],
        exclusionary_flags=exclusionary_flags,
        requirement_assessments=requirement_assessments,
        confidence=confidence,
    )
    return CandidateResult(
        candidate_id=candidate_id,
        source_path=f"{candidate_id}.txt",
        name=f"Candidate {candidate_id}",
        fit_assessment=fit_assessment,
        interview_questions=[InterviewQuestion(
            question="Q?",
            validates_requirement_id="req-1",
            validates_requirement="Requirement 1",
            gap_type="technical_depth",
            rationale="Rationale",
            expected_positive_evidence="Evidence",
            expected_warning_signals=["Warning"],
            potential_fit_increase=5.0,
            priority=1,
        )],
        retrieval_score=retrieval_score,
    )


def test_ranking_agent_sorts_by_fit_percentage():
    agent = RankingAgent()
    payload = {
        "job_description": {"role_id": "r1", "role_title": "Data Analyst"},
        "candidate_fit_results": [
            build_candidate("c1", 62.0, 40.0, 0.7),
            build_candidate("c2", 78.0, 55.0, 0.6),
            build_candidate("c3", 55.0, 30.0, 0.8),
        ],
        "ranking_config": {},
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result["ranking"][0]["candidate_id"] == "c2"
    assert result["ranking"][1]["candidate_id"] == "c1"
    assert result["ranking"][2]["candidate_id"] == "c3"


def test_ranking_agent_applies_tiebreakers():
    agent = RankingAgent()
    requirement_assessments = [RequirementAssessment(requirement_id="req1", requirement_name="Req 1", mandatory=True, exclusionary=False, status="met", raw_score=1.0, max_score=1.0, weighted_score=1.0, evidence=[], gap_description="", confidence=0.9)]
    payload = {
        "job_description": {"role_id": "r1", "role_title": "Data Analyst"},
        "candidate_fit_results": [
            build_candidate("c1", 80.0, 50.0, 0.7, retrieval_score=0.2, requirement_assessments=requirement_assessments),
            build_candidate("c2", 80.0, 45.0, 0.9, retrieval_score=0.1, requirement_assessments=requirement_assessments),
            build_candidate("c3", 80.0, 50.0, 0.7, retrieval_score=0.3, requirement_assessments=requirement_assessments),
        ],
        "ranking_config": {},
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result["ranking"][0]["candidate_id"] == "c3"
    assert result["ranking"][1]["candidate_id"] == "c1"
    assert result["ranking"][2]["candidate_id"] == "c2"


def test_ranking_agent_filters_by_fit_minimum():
    agent = RankingAgent()
    payload = {
        "job_description": {"role_id": "r1", "role_title": "Data Analyst"},
        "candidate_fit_results": [
            build_candidate("c1", 49.0, 30.0, 0.8),
            build_candidate("c2", 51.0, 40.0, 0.7),
        ],
        "ranking_config": {"fit_minimum": 50.0},
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert len(result["ranking"]) == 1
    assert result["ranking"][0]["candidate_id"] == "c2"


def test_ranking_agent_handles_exclusionary_flags():
    agent = RankingAgent()
    payload = {
        "job_description": {"role_id": "r1", "role_title": "Data Analyst"},
        "candidate_fit_results": [
            build_candidate("c1", 85.0, 55.0, 0.9, exclusionary_flags=["Req X"]),
            build_candidate("c2", 82.0, 50.0, 0.8),
        ],
        "ranking_config": {"include_exclusionary_missing": True},
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert len(result["ranking"]) == 2
    assert result["ranking"][0]["candidate_id"] == "c1"
    assert result["ranking"][0]["recommendation"] == "do_not_advance"


def test_ranking_agent_stable_ordering():
    agent = RankingAgent()
    payload = {
        "job_description": {"role_id": "r1", "role_title": "Data Analyst"},
        "candidate_fit_results": [
            build_candidate("c1", 65.0, 40.0, 0.7, retrieval_score=0.1),
            build_candidate("c2", 65.0, 40.0, 0.7, retrieval_score=0.2),
            build_candidate("c3", 65.0, 40.0, 0.7, retrieval_score=0.1),
        ],
        "ranking_config": {},
    }

    result, _ = asyncio.run(agent.execute(payload))
    assert result["ranking"][0]["candidate_id"] == "c2"
    assert result["ranking"][1]["candidate_id"] in {"c1", "c3"}
    assert result["ranking"][2]["candidate_id"] in {"c1", "c3"}
    assert result["ranking"][1]["candidate_id"] != result["ranking"][2]["candidate_id"]
