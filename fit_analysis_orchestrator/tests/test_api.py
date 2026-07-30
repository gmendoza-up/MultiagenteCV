# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from fit_analysis_orchestrator.api import app
from fit_analysis_orchestrator.models import FitAnalysisResult, SupervisorResult, TraceEntry


class DummyChroma:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


class DummyOrchestrator:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def run(self) -> FitAnalysisResult:
        return FitAnalysisResult(
            analysis_id="test-analysis",
            role={"description_text": "Role text sample"},
            candidates_analyzed=0,
            ranking=[],
            supervisor_result=SupervisorResult(status="approved"),
            traces=[
                TraceEntry(
                    step="JobDescriptionAgent",
                    agent="JobDescriptionAgent",
                    status="completed",
                    start_time="2025-01-01T00:00:00Z",
                    end_time="2025-01-01T00:00:01Z",
                    latency_ms=1000,
                )
            ],
            total_latency_ms=1000,
            total_tokens=0,
            status="completed",
            errors=[],
        )


def build_test_session_local():
    engine = create_engine("sqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_returns_ready(monkeypatch):
    session_local = build_test_session_local()
    monkeypatch.setattr("fit_analysis_orchestrator.api.SessionLocal", session_local)
    monkeypatch.setattr("fit_analysis_orchestrator.api.ChromaVectorRepository", DummyChroma)

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_endpoint_returns_unavailable_when_chroma_fails(monkeypatch):
    session_local = build_test_session_local()
    monkeypatch.setattr("fit_analysis_orchestrator.api.SessionLocal", session_local)

    class FailingChroma:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Chroma unavailable")

    monkeypatch.setattr("fit_analysis_orchestrator.api.ChromaVectorRepository", FailingChroma)

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 503
    assert "Chroma readiness check failed" in response.json()["error"]


def test_analyze_endpoint_invokes_orchestrator(monkeypatch):
    monkeypatch.setattr("fit_analysis_orchestrator.api.FitAnalysisOrchestrator", DummyOrchestrator)

    client = TestClient(app)
    response = client.post(
        "/analyze",
        json={
            "role_description": "Buscamos un ingeniero de datos con experiencia en Python.",
            "cv_directory": "./cvs",
            "top_k_candidates": 2,
            "weights": {"technical": 0.7},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_id"] == "test-analysis"
    assert payload["status"] == "completed"


def test_get_analysis_returns_not_found(monkeypatch):
    class MissingRepository:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def get(self, analysis_id: str) -> Any:
            return None

    monkeypatch.setattr("fit_analysis_orchestrator.api.AnalysisRepository", MissingRepository)
    client = TestClient(app)
    response = client.get("/analyses/nonexistent")

    assert response.status_code == 404
    assert response.json()["error"] == "Analysis not found"
