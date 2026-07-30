# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fit_analysis_orchestrator.candidate_profile_agent import CandidateProfileAgent
from fit_analysis_orchestrator.models import CandidateProfile


def test_candidate_profile_complete_dates():
    agent = CandidateProfileAgent()
    payload = {
        "candidate_id": "c1",
        "cv_chunks": [
            {
                "content": "Nombre: Ana Pérez\nEmpresa: Acme Corp\nPuesto: Ingeniera de Datos\nDesde: enero 2019 hasta diciembre 2022\nResponsabilidades: Diseño de pipelines, análisis de datos.",
                "source_file": "c1.txt",
                "page": 1,
                "section": "Experiencia",
            }
        ],
        "source_file": "c1.txt",
    }

    profile, tokens = asyncio.run(agent.execute(payload))

    assert isinstance(profile, CandidateProfile)
    assert profile.candidate_name == "Ana Pérez"
    assert profile.total_years_experience == 3.0
    assert profile.technologies == []
    assert profile.experiences[0].company == "Acme Corp"
    assert profile.confidence >= 0.8


def test_candidate_profile_without_dates():
    agent = CandidateProfileAgent()
    payload = {
        "candidate_id": "c2",
        "cv_chunks": [
            {
                "content": "Nombre: Luis Martínez\nPuesto: Analista TI\nResponsabilidades: Soporte de redes y administración de servidores.",
                "source_file": "c2.txt",
                "page": 1,
                "section": "Experiencia",
            }
        ],
        "source_file": "c2.txt",
    }

    profile, tokens = asyncio.run(agent.execute(payload))
    assert profile.total_years_experience == 0.0
    assert profile.candidate_name == "Luis Martínez"
    assert profile.confidence >= 0.2


def test_candidate_profile_overlapping_experience():
    agent = CandidateProfileAgent()
    payload = {
        "candidate_id": "c3",
        "cv_chunks": [
            {
                "content": "Nombre: Carla Gómez\nEmpresa: Fintech S.A.\nPuesto: Consultora de Datos\nDesde: enero 2020 hasta diciembre 2021\nResponsabilidades: Modelado financiero.",
                "source_file": "c3.txt",
                "page": 1,
                "section": "Experiencia",
            },
            {
                "content": "Empresa: Fintech S.A.\nPuesto: Analista Senior\nDesde: marzo 2021 hasta diciembre 2022\nResponsabilidades: Implementación de KPIs.",
                "source_file": "c3.txt",
                "page": 2,
                "section": "Experiencia",
            }
        ],
        "source_file": "c3.txt",
    }

    profile, tokens = asyncio.run(agent.execute(payload))
    assert profile.total_years_experience == 4.0
    assert len(profile.experiences) == 2


def test_candidate_profile_technology_without_context():
    agent = CandidateProfileAgent()
    payload = {
        "candidate_id": "c4",
        "cv_chunks": [
            {
                "content": "Experiencia con Python y Docker.",
                "source_file": "c4.txt",
                "page": 1,
                "section": "Resumen",
            }
        ],
        "source_file": "c4.txt",
    }

    profile, tokens = asyncio.run(agent.execute(payload))
    assert any(tech.value.lower() == "python" for tech in profile.technologies)
    assert any(tech.value.lower() == "docker" for tech in profile.technologies)
    assert profile.total_years_experience == 0.0


def test_candidate_profile_excludes_sensitive_information():
    agent = CandidateProfileAgent()
    payload = {
        "candidate_id": "c5",
        "cv_chunks": [
            {
                "content": "Nombre: Marta Ríos\nEdad: 30\nEmpresa: DataLabs\nPuesto: Ingeniera\nResponsabilidades: Desarrollo de ETL.",
                "source_file": "c5.txt",
                "page": 1,
                "section": "Experiencia",
            }
        ],
        "source_file": "c5.txt",
    }

    profile, tokens = asyncio.run(agent.execute(payload))
    assert all("edad" not in evidence.evidence_text.lower() for evidence in profile.evidence)
    assert profile.candidate_name == "Marta Ríos"
