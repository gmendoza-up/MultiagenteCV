# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fit_analysis_orchestrator.interview_question_agent import InterviewQuestionAgent
from fit_analysis_orchestrator.models import CandidateProfile, RoleDescriptor, EvidenceDetail, InterviewQuestion


def create_profile_with_technologies() -> CandidateProfile:
    return CandidateProfile(
        candidate_id="c1",
        candidate_name="Candidato Ejemplo",
        summary="Experiencia en desarrollo de pipelines y comunicación con clientes.",
        total_years_experience=4.0,
        technologies=[
            EvidenceDetail(value="Python", evidence_text="Python", source_file="cv.txt", page=1, section="Resumen", evidence_type="technology", confidence=0.9),
            EvidenceDetail(value="SQL", evidence_text="SQL", source_file="cv.txt", page=1, section="Resumen", evidence_type="technology", confidence=0.8),
        ],
        skills=[
            EvidenceDetail(value="Comunicación efectiva", evidence_text="Comunicación efectiva.", source_file="cv.txt", page=1, section="Resumen", evidence_type="skill", confidence=0.8),
        ],
    )


def test_interview_question_agent_returns_five_questions():
    agent = InterviewQuestionAgent()
    profile = create_profile_with_technologies()
    role = RoleDescriptor(
        description_text="Buscamos un analista de datos con experiencia en Python, SQL y comunicación con stakeholders.",
        source="test",
    )

    questions, tokens = asyncio.run(agent.execute(profile, role))

    assert len(questions) == 5
    assert tokens >= 22
    assert all(isinstance(question, InterviewQuestion) for question in questions)
    assert len({question.question for question in questions}) == 5
    assert all(1 <= question.priority <= 5 for question in questions)
    assert any("Python" in question.question or "SQL" in question.question or "stakeholders" in question.question for question in questions)


def test_interview_question_agent_uses_missing_requirements_first():
    agent = InterviewQuestionAgent()
    profile = CandidateProfile(
        candidate_id="c2",
        candidate_name="Candidato Falta",
        summary="Experiencia en análisis y resultados.",
        total_years_experience=2.0,
        technologies=[
            EvidenceDetail(value="Excel", evidence_text="Excel", source_file="cv.txt", page=1, section="Resumen", evidence_type="technology", confidence=0.7),
        ],
        skills=[
            EvidenceDetail(value="Análisis", evidence_text="Análisis", source_file="cv.txt", page=1, section="Resumen", evidence_type="skill", confidence=0.7),
        ],
    )
    role = RoleDescriptor(
        description_text="Se requiere experiencia en Python, SQL, trabajo con stakeholders y comunicación clara.",
        source="test",
    )

    questions, _ = asyncio.run(agent.execute(profile, role))

    assert len(questions) == 5
    assert questions[0].validates_requirement_id.startswith("se-requiere-experiencia-en-python") or "python" in questions[0].validates_requirement.lower()
    assert any("stakeholders" in question.validates_requirement.lower() for question in questions)


def test_interview_question_agent_avoids_sensitive_content():
    agent = InterviewQuestionAgent()
    profile = create_profile_with_technologies()
    role = RoleDescriptor(
        description_text="Buscamos un líder que comunique bien y gestione equipos sin referencias de edad o género.",
        source="test",
    )

    questions, _ = asyncio.run(agent.execute(profile, role))
    assert len(questions) == 5
    assert all(not any(term in question.question.lower() for term in ["edad", "género", "genero", "nacionalidad", "dirección", "direccion", "estado civil", "fotografía", "foto", "religión", "salud", "casado", "hijo", "hijos", "matrimonio"]) for question in questions)


def test_interview_question_agent_potential_fit_increase_is_reasonable():
    agent = InterviewQuestionAgent()
    profile = create_profile_with_technologies()
    role = RoleDescriptor(
        description_text="Requerimos habilidades en Python, SQL, AWS, Docker y comunicación.",
        source="test",
    )

    questions, _ = asyncio.run(agent.execute(profile, role))
    total_improvement = sum(question.potential_fit_increase for question in questions)

    assert total_improvement <= 55.0
    assert all(question.potential_fit_increase >= 3.0 for question in questions)
