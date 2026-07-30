# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from fit_analysis_orchestrator import db
from fit_analysis_orchestrator.models_sql import AnalysisRun, CandidateResult, AgentTrace, SupervisorResult
from fit_analysis_orchestrator.repositories import (
    AnalysisRepository,
    CandidateResultRepository,
    AgentTraceRepository,
    SupervisorResultRepository,
)


def setup_function() -> None:
    db.Base.metadata.drop_all(bind=db.engine)
    db.Base.metadata.create_all(bind=db.engine)


def test_analysis_repository_crud():
    session = db.SessionLocal()
    repo = AnalysisRepository(session)

    data = {
        "analysis_id": "a1",
        "role_id": "r1",
        "start_time": datetime.utcnow(),
        "end_time": datetime.utcnow(),
        "status": "completed",
        "candidates_analyzed": 3,
        "total_latency_ms": 1000,
        "total_tokens": 30,
    }

    analysis = repo.create(data)
    assert isinstance(analysis, AnalysisRun)
    assert analysis.analysis_id == "a1"

    fetched = repo.get("a1")
    assert fetched is not None
    assert fetched.analysis_id == "a1"

    updated = repo.update("a1", {"status": "failed", "total_tokens": 40})
    assert updated is not None
    assert updated.status == "failed"
    assert updated.total_tokens == 40

    session.close()


def test_candidate_result_repository():
    session = db.SessionLocal()
    repo = CandidateResultRepository(session)

    data = {
        "analysis_id": "a1",
        "candidate_id": "c1",
        "candidate_name": "Candidate One",
        "fit_percentage": 85.0,
        "rank": 1,
        "recommendation": "advance",
        "confidence": 0.9,
    }

    candidate = repo.create(data)
    assert isinstance(candidate, CandidateResult)
    assert candidate.candidate_id == "c1"

    results = repo.list_by_analysis("a1")
    assert len(results) == 1
    assert results[0].candidate_id == "c1"

    session.close()


def test_agent_trace_repository():
    session = db.SessionLocal()
    repo = AgentTraceRepository(session)

    data = {
        "analysis_id": "a1",
        "agent_name": "JobDescriptionAgent",
        "start_time": datetime.utcnow(),
        "end_time": datetime.utcnow(),
        "latency_ms": 150,
        "tokens": 5,
        "status": "completed",
        "error": None,
    }

    trace = repo.create(data)
    assert isinstance(trace, AgentTrace)
    assert trace.agent_name == "JobDescriptionAgent"

    traces = repo.list_by_analysis("a1")
    assert len(traces) == 1
    assert traces[0].latency_ms == 150

    session.close()


def test_supervisor_result_repository():
    session = db.SessionLocal()
    repo = SupervisorResultRepository(session)

    data = {
        "analysis_id": "a1",
        "decision": "approved",
        "quality_score": 0.8,
        "issues_json": ["none"],
        "flags_json": ["none"],
    }

    supervisor = repo.create(data)
    assert isinstance(supervisor, SupervisorResult)
    assert supervisor.decision == "approved"

    fetched = repo.get_by_analysis("a1")
    assert fetched is not None
    assert fetched.quality_score == 0.8

    session.close()
