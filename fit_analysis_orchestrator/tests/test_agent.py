# -*- coding: utf-8 -*-
import asyncio
import json
from pathlib import Path

import pytest

from fit_analysis_orchestrator.agent import FitAnalysisOrchestrator


def create_dummy_cvs(tmp_path: Path, count: int = 3) -> Path:
    for index in range(count):
        file_path = tmp_path / f"candidato_{index}.txt"
        file_path.write_text(
            f"Nombre: Candidato {index}\nExperiencia: 5 años en Python y análisis de datos."
        )
    return tmp_path


def test_orchestrator_completes_successfully(tmp_path: Path):
    cv_dir = create_dummy_cvs(tmp_path, count=3)
    orchestrator = FitAnalysisOrchestrator(
        role_text="Buscamos un ingeniero de datos con experiencia en Python, SQL y comunicación efectiva.",
        cv_directory=str(cv_dir),
        weights=json.loads('{"technical": 0.7, "cultural": 0.3}'),
        max_candidates=2,
    )
    result = asyncio.run(orchestrator.run())

    assert result.status == "completed"
    assert result.candidates_analyzed == 2
    assert len(result.ranking) == 2
    assert result.supervisor_result.status == "approved"
    assert result.total_latency_ms >= 0
    assert result.total_tokens > 0


def test_orchestrator_applies_supervisor_modifications(tmp_path: Path):
    cv_dir = create_dummy_cvs(tmp_path, count=1)
    orchestrator = FitAnalysisOrchestrator(
        role_text="Revisar este rol y modificar la clasificación según prioridades.",
        cv_directory=str(cv_dir),
        weights=json.loads('{"technical": 0.5}'),
        max_candidates=1,
    )
    result = asyncio.run(orchestrator.run())

    assert result.status == "completed"
    assert result.supervisor_result.status == "modified_and_approved"
    assert result.supervisor_result.modifications is not None
    assert any("note" in entry for entry in result.ranking)


def test_orchestrator_returns_rejected_when_supervisor_denies(tmp_path: Path):
    cv_dir = create_dummy_cvs(tmp_path, count=1)
    orchestrator = FitAnalysisOrchestrator(
        role_text="Este rol debe rechazar porque no cumple requisitos mínimos.",
        cv_directory=str(cv_dir),
        weights=json.loads('{"technical": 0.3}'),
        max_candidates=1,
    )
    result = asyncio.run(orchestrator.run())

    assert result.status == "rejected"
    assert result.supervisor_result.status == "rejected"
    assert result.ranking == []


def test_orchestrator_validates_insufficient_role_description(tmp_path: Path):
    cv_dir = create_dummy_cvs(tmp_path, count=1)
    orchestrator = FitAnalysisOrchestrator(
        role_text="Muy corto.",
        cv_directory=str(cv_dir),
        weights=json.loads('{"technical": 0.5}'),
        max_candidates=1,
    )
    result = asyncio.run(orchestrator.run())

    assert result.status == "rejected"
    assert result.supervisor_result.status == "rejected"
    assert any("insuficiente" in error["error"].lower() for error in result.errors)
