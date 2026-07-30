# -*- coding: utf-8 -*-
import asyncio
import json
from pathlib import Path

import pytest

from fit_analysis_orchestrator import db
from fit_analysis_orchestrator.agent import FitAnalysisOrchestrator
from fit_analysis_orchestrator.models_sql import AnalysisRun, CandidateResult, AgentTrace, SupervisorResult


def create_dummy_cvs(tmp_path: Path, count: int = 2) -> Path:
    for index in range(count):
        file_path = tmp_path / f"candidato_{index}.txt"
        file_path.write_text(
            f"Nombre: Candidato {index}\nExperiencia: 5 años en Python y análisis de datos."
        )
    return tmp_path


def setup_function() -> None:
    db.Base.metadata.drop_all(bind=db.engine)
    db.Base.metadata.create_all(bind=db.engine)


def test_orchestrator_persists_analysis_results(tmp_path: Path):
    cv_dir = create_dummy_cvs(tmp_path, count=2)
    orchestrator = FitAnalysisOrchestrator(
        role_text="Buscamos un ingeniero de datos con experiencia en Python, SQL y comunicación efectiva.",
        cv_directory=str(cv_dir),
        weights=json.loads('{"technical": 0.7, "cultural": 0.3}'),
        max_candidates=2,
    )

    result = asyncio.run(orchestrator.run())

    assert result.status == "completed"

    session = db.SessionLocal()
    analysis = session.get(AnalysisRun, result.analysis_id)
    assert analysis is not None
    assert analysis.analysis_id == result.analysis_id
    assert analysis.candidates_analyzed == result.candidates_analyzed
    assert analysis.status == result.status
    assert analysis.role_json["description_text"].startswith("Buscamos un ingeniero")
    assert isinstance(analysis.ranking_json, list)
    assert analysis.errors_json == result.errors
    assert isinstance(analysis.supervisor_json, dict)

    traces = session.query(AgentTrace).filter_by(analysis_id=result.analysis_id).all()
    assert traces
    assert all(trace.analysis_id == result.analysis_id for trace in traces)

    supervisor = session.query(SupervisorResult).filter_by(analysis_id=result.analysis_id).one_or_none()
    assert supervisor is not None
    assert supervisor.decision == result.supervisor_result.status
    session.close()


def test_orchestrator_continues_on_persistence_failure(tmp_path: Path, monkeypatch):
    cv_dir = create_dummy_cvs(tmp_path, count=1)
    orchestrator = FitAnalysisOrchestrator(
        role_text="Revisar este rol y verificar persistencia.",
        cv_directory=str(cv_dir),
        weights=json.loads('{"technical": 0.5}'),
        max_candidates=1,
    )

    def raise_commit(*args, **kwargs):
        raise RuntimeError("DB commit failed")

    monkeypatch.setattr(orchestrator._db_session, "commit", raise_commit)

    result = asyncio.run(orchestrator.run())

    assert result.status in {"completed", "rejected"}
    assert any(error["step"] == "Persistence" for error in result.errors)
    assert "DB commit failed" in result.errors[-1]["error"]
