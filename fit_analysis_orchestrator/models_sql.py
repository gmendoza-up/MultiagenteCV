# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    analysis_id: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    role_id: Mapped[str] = mapped_column(String(128), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidates_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    role_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    ranking_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    errors_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    supervisor_json: Mapped[Any] = mapped_column(JSON, nullable=True)

    candidates: Mapped[list["CandidateResult"]] = relationship("CandidateResult", back_populates="analysis", cascade="all, delete-orphan")
    traces: Mapped[list["AgentTrace"]] = relationship("AgentTrace", back_populates="analysis", cascade="all, delete-orphan")
    supervisor: Mapped["SupervisorResult"] = relationship("SupervisorResult", back_populates="analysis", uselist=False, cascade="all, delete-orphan")


class CandidateResult(Base):
    __tablename__ = "candidate_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(128), ForeignKey("analysis_runs.analysis_id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(256), nullable=True)
    fit_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    result_json: Mapped[Any] = mapped_column(JSON, nullable=True)

    analysis: Mapped[AnalysisRun] = relationship("AnalysisRun", back_populates="candidates")


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(128), ForeignKey("analysis_runs.analysis_id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=True)

    analysis: Mapped[AnalysisRun] = relationship("AnalysisRun", back_populates="traces")


class SupervisorResult(Base):
    __tablename__ = "supervisor_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(128), ForeignKey("analysis_runs.analysis_id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    dimension_scores: Mapped[Any] = mapped_column(JSON, nullable=True)
    issues_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    flags_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    modifications_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    final_result: Mapped[Any] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)

    analysis: Mapped[AnalysisRun] = relationship("AnalysisRun", back_populates="supervisor")
