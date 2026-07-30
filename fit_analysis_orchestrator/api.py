# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .agent import FitAnalysisOrchestrator
from .cv_indexing_pipeline import CVIndexingPipeline, CVIndexingRequest, CVIndexingSummary
from .db import SessionLocal
from .models import FitAnalysisResult
from .repositories import AnalysisRepository
from .vector_repository import ChromaVectorRepository

LOGGER = logging.getLogger("FitAnalysisAPI")
handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)
handler.setFormatter(formatter)
LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)

app = FastAPI(
    title="MultiagenteCV API",
    description="API REST para indexar CVs y ejecutar el análisis de compatibilidad multiagente.",
    version="0.1.0",
)

DEFAULT_CV_DIRECTORY = os.getenv("CV_DIRECTORY", "./cvs")


class AnalyzeRequest(BaseModel):
    role_description: str = Field(..., min_length=10)
    cv_directory: Optional[str] = None
    top_k_candidates: int = Field(default=10, ge=1)
    weights: Dict[str, float] = Field(default_factory=dict)
    analysis_id: Optional[str] = None


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    LOGGER.warning("HTTP error: %s %s", request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"},
    )


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _check_sql_ready(db: Any) -> None:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError(f"SQL readiness check failed: {exc}") from exc


def _check_chroma_ready() -> None:
    try:
        ChromaVectorRepository()
    except Exception as exc:
        raise RuntimeError(f"Chroma readiness check failed: {exc}") from exc


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(db: Any = Depends(get_db_session)) -> Dict[str, str]:
    try:
        _check_sql_ready(db)
        _check_chroma_ready()
        return {"status": "ready"}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@app.post("/index-cvs", response_model=CVIndexingSummary)
async def index_cvs(request: CVIndexingRequest) -> CVIndexingSummary:
    pipeline = CVIndexingPipeline()
    try:
        result = await pipeline.index(request)
        return result
    except Exception as exc:
        LOGGER.exception("Indexing pipeline failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to index CVs") from exc


@app.post("/analyze", response_model=FitAnalysisResult)
async def analyze(request: AnalyzeRequest) -> FitAnalysisResult:
    pipeline = FitAnalysisOrchestrator(
        role_text=request.role_description,
        cv_directory=request.cv_directory or os.getenv("CV_DIRECTORY", DEFAULT_CV_DIRECTORY),
        weights=request.weights,
        max_candidates=request.top_k_candidates,
        run_id=request.analysis_id,
    )
    try:
        result = await pipeline.run()
        return result
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Analysis execution failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to execute analysis")


@app.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, db: Any = Depends(get_db_session)) -> Dict[str, Any]:
    repository = AnalysisRepository(db)
    analysis = repository.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    return {
        "analysis_id": analysis.analysis_id,
        "role": analysis.role_json,
        "status": analysis.status,
        "candidates_analyzed": analysis.candidates_analyzed,
        "total_latency_ms": analysis.total_latency_ms,
        "total_tokens": analysis.total_tokens,
        "ranking": analysis.ranking_json,
        "errors": analysis.errors_json,
        "supervisor": analysis.supervisor_json,
    }


@app.get("/analyses/{analysis_id}/ranking")
async def get_analysis_ranking(analysis_id: str, db: Any = Depends(get_db_session)) -> Dict[str, Any]:
    repository = AnalysisRepository(db)
    analysis = repository.get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return {"analysis_id": analysis.analysis_id, "ranking": analysis.ranking_json}
