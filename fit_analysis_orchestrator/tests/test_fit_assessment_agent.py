# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fit_analysis_orchestrator.fit_assessment_agent import FitAssessmentAgent
from fit_analysis_orchestrator.models import CandidateProfile, EvidenceDetail


def base_profile() -> CandidateProfile:
    profile = CandidateProfile(
        candidate_id="c1",
        candidate_name="Ana",
        summary="Perfil técnico con experiencia en Python y AWS.",
        professional_summary="Ingeniera de datos con experiencia en Python y AWS.",
        total_years_experience=5.0,
        evidence=[
            EvidenceDetail(
                value="Python",
                evidence_text="Desarrollo en Python para ETL y análisis.",
                source_file="c1.txt",
                page=1,
                section="Experiencia",
                evidence_type="explicit",
                confidence=0.9,
            ),
            EvidenceDetail(
                value="AWS",
                evidence_text="Implementación en AWS con S3 y Lambda.",
                source_file="c1.txt",
                page=1,
                section="Experiencia",
                evidence_type="explicit",
                confidence=0.8,
            ),
        ],
        technologies=[
            EvidenceDetail(
                value="Python",
                evidence_text="Python",
                source_file="c1.txt",
                page=1,
                section="Experiencia",
                evidence_type="explicit",
                confidence=0.9,
            )
        ],
        certifications=[],
        skills=[],
        education=[],
        languages=[],
    )
    return profile


def test_fit_assessment_high_fit():
    agent = FitAssessmentAgent()
    profile = base_profile()
    payload = {
        "job_description": {
            "requirements": [
                {"requirement_id": "r1", "name": "Python", "mandatory": True, "exclusionary": False, "weight": 10.0},
                {"requirement_id": "r2", "name": "AWS", "mandatory": False, "exclusionary": False, "weight": 5.0},
            ]
        },
        "candidate_profile": profile,
        "scoring_config": {
            "mandatory_requirements": 50.0,
            "relevant_experience": 20.0,
            "technologies_tools": 15.0,
            "education_certifications": 10.0,
            "desirable_requirements": 5.0,
        },
    }

    assessment, tokens = asyncio.run(agent.execute(payload))
    assert assessment.fit_percentage <= 100.0
    assert assessment.fit_level == "high"
    assert assessment.mandatory_fit >= 50.0
    assert any(req.requirement_id == "r1" for req in assessment.requirement_assessments)


def test_fit_assessment_medium_fit():
    agent = FitAssessmentAgent()
    profile = base_profile()
    profile.total_years_experience = 1.0
    payload = {
        "job_description": {
            "requirements": [
                {"requirement_id": "r1", "name": "5 años de experiencia", "mandatory": True, "exclusionary": False, "weight": 10.0, "minimum_years": 5},
                {"requirement_id": "r2", "name": "AWS", "mandatory": False, "exclusionary": False, "weight": 5.0},
            ]
        },
        "candidate_profile": profile,
        "scoring_config": {},
    }

    assessment, tokens = asyncio.run(agent.execute(payload))
    assert assessment.fit_percentage >= 0.0
    assert assessment.fit_percentage <= 100.0
    assert assessment.fit_level in {"medium", "low"}
    assert any(req.status == "not_evidenced" for req in assessment.requirement_assessments)


def test_fit_assessment_low_evidence():
    agent = FitAssessmentAgent()
    profile = CandidateProfile(
        candidate_id="c2",
        candidate_name="Luis",
        summary="Perfil sin evidencia clara.",
        professional_summary="",
        total_years_experience=0.0,
        evidence=[],
        technologies=[],
        certifications=[],
        skills=[],
        education=[],
        languages=[],
    )
    payload = {
        "job_description": {
            "requirements": [
                {"requirement_id": "r1", "name": "Python", "mandatory": True, "exclusionary": False, "weight": 10.0},
            ]
        },
        "candidate_profile": profile,
        "scoring_config": {},
    }

    assessment, tokens = asyncio.run(agent.execute(payload))
    assert assessment.fit_percentage == 0.0
    assert assessment.requirement_assessments[0].status == "not_evidenced"
    assert assessment.confidence <= 0.5


def test_fit_assessment_exclusionary_missing():
    agent = FitAssessmentAgent()
    profile = base_profile()
    payload = {
        "job_description": {
            "requirements": [
                {"requirement_id": "r1", "name": "Python", "mandatory": True, "exclusionary": False, "weight": 10.0},
                {"requirement_id": "r2", "name": "No experiencia en Java", "mandatory": True, "exclusionary": True, "weight": 10.0},
            ]
        },
        "candidate_profile": profile,
        "scoring_config": {"exclusionary_penalty": 30.0},
    }

    assessment, tokens = asyncio.run(agent.execute(payload))
    assert "No experiencia en Java" in assessment.exclusionary_flags
    assert assessment.fit_percentage <= 70.0


def test_fit_assessment_weights_invalid_normalize():
    agent = FitAssessmentAgent()
    profile = base_profile()
    payload = {
        "job_description": {
            "requirements": [
                {"requirement_id": "r1", "name": "Python", "mandatory": True, "exclusionary": False, "weight": 10.0},
            ]
        },
        "candidate_profile": profile,
        "scoring_config": {"mandatory_requirements": 30.0, "relevant_experience": 20.0, "technologies_tools": 10.0, "education_certifications": 10.0, "desirable_requirements": 5.0},
    }

    assessment, tokens = asyncio.run(agent.execute(payload))
    assert assessment.fit_percentage >= 0.0
    assert assessment.fit_percentage <= 100.0
