# -*- coding: utf-8 -*-
import asyncio
import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from job_description_agent.agent import JobDescriptionAgent
from job_description_agent.models import WeightConfig


def test_job_description_complete():
    payload = {
        "role_id": "r1",
        "role_description": (
            "Senior Data Engineer\n\n"
            "Buscamos un ingeniero de datos responsable de construir pipelines robustos, "
            "optimizar procesos ETL y garantizar la calidad de los datos.\n\n"
            "Responsabilidades:\n"
            "- Diseñar y mantener sistemas de ingesta de datos.\n"
            "- Colaborar con el equipo de ciencia de datos.\n\n"
            "Requisitos obligatorios:\n"
            "- 5 años de experiencia en ingeniería de datos.\n"
            "- Experiencia sólida en Python, SQL y AWS.\n"
            "- Título universitario en Ingeniería, Ciencias de la Computación o afín.\n\n"
            "Requisitos deseables:\n"
            "- Certificación AWS Certified Data Analytics.\n"
            "- Conocimientos en Docker y Kubernetes.\n"
        )
    }
    agent = JobDescriptionAgent(config_weights=WeightConfig(weights={
        "mandatory_requirements": 50.0,
        "relevant_experience": 20.0,
        "technologies_tools": 15.0,
        "education_certifications": 10.0,
        "desirable_requirements": 5.0,
    }).weights)
    result = asyncio.run(agent.execute(payload))

    assert result.role_id == "r1"
    assert "Senior Data Engineer" in result.role_title
    assert len(result.responsibilities) >= 2
    assert any("Python" in req.source_text for req in result.requirements)
    assert any("AWS" in req.source_text for req in result.requirements)
    assert result.weights["mandatory_requirements"] == 50.0
    assert result.confidence >= 0.8


def test_job_description_ambiguous():
    payload = {
        "role_id": "r2",
        "role_description": (
            "Analista de negocios\n\n"
            "Se busca una persona que idealmente tenga experiencia con análisis de datos, "
            "aunque no es estrictamente obligatorio.\n\n"
            "Requisitos:\n"
            "- Manejo de SQL.\n"
            "- Preferible conocimiento en Power BI.\n"
        )
    }
    agent = JobDescriptionAgent(config_weights=WeightConfig(weights={
        "mandatory_requirements": 50.0,
        "relevant_experience": 20.0,
        "technologies_tools": 15.0,
        "education_certifications": 10.0,
        "desirable_requirements": 5.0,
    }).weights)
    result = asyncio.run(agent.execute(payload))

    assert result.role_id == "r2"
    assert any(req.ambiguous for req in result.requirements)
    assert any("SQL" in req.source_text for req in result.requirements)
    assert len(result.clarification_questions) >= 1


def test_job_description_duplicate_requirements():
    payload = {
        "role_id": "r3",
        "role_description": (
            "Ingeniero DevOps\n\n"
            "Requisitos:\n"
            "- Experiencia con Docker.\n"
            "- Manejo de Docker y contenedores.\n"
            "- Conocimiento en Kubernetes.\n"
        )
    }
    agent = JobDescriptionAgent(config_weights=WeightConfig(weights={
        "mandatory_requirements": 50.0,
        "relevant_experience": 20.0,
        "technologies_tools": 15.0,
        "education_certifications": 10.0,
        "desirable_requirements": 5.0,
    }).weights)
    result = asyncio.run(agent.execute(payload))

    names = [req.name.lower() for req in result.requirements]
    assert any("docker" in name for name in names)
    assert len(result.requirements) <= 3


def test_job_description_missing_experience_years():
    payload = {
        "role_id": "r4",
        "role_description": (
            "Consultor TI\n\n"
            "Se requiere conocimiento en gestión de proyectos y experiencia en IT.\n"
            "Responsabilidades:\n"
            "- Coordinar equipos.\n"
            "- Asegurar la entrega de soluciones.\n"
        )
    }
    agent = JobDescriptionAgent(config_weights=WeightConfig(weights={
        "mandatory_requirements": 50.0,
        "relevant_experience": 20.0,
        "technologies_tools": 15.0,
        "education_certifications": 10.0,
        "desirable_requirements": 5.0,
    }).weights)
    result = asyncio.run(agent.execute(payload))

    assert "años" not in result.role_summary.lower() or all(req.minimum_years is None for req in result.requirements)
    assert any("experiencia" in q.lower() for q in result.clarification_questions)


def test_job_description_mandatory_and_desirable_mixed():
    payload = {
        "role_id": "r5",
        "role_description": (
            "Especialista en Marketing\n\n"
            "Requisitos obligatorios:\n"
            "- 3 años en marketing digital.\n"
            "- Conocimientos en Google Analytics.\n\n"
            "Requisitos deseables:\n"
            "- Experiencia con HubSpot.\n"
            "- Deseable manejo de SEO.\n"
        )
    }
    agent = JobDescriptionAgent(config_weights=WeightConfig(weights={
        "mandatory_requirements": 50.0,
        "relevant_experience": 20.0,
        "technologies_tools": 15.0,
        "education_certifications": 10.0,
        "desirable_requirements": 5.0,
    }).weights)
    result = asyncio.run(agent.execute(payload))

    mandatory = [req for req in result.requirements if req.mandatory]
    desirable = [req for req in result.requirements if not req.mandatory]
    assert any("Google Analytics" in req.source_text for req in mandatory)
    assert any("SEO" in req.source_text for req in desirable)
