# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WeightConfig(BaseModel):
    weights: Dict[str, float] = Field(default_factory=dict)


class RoleDescriptor(BaseModel):
    description_text: str
    source: str
    summary: Optional[str] = None
    validated: bool = False


class EvidenceDetail(BaseModel):
    value: str
    evidence_text: str
    source_file: str
    page: int = 0
    section: str = ""
    evidence_type: str
    confidence: float = 0.0


class ExperienceEntry(BaseModel):
    title: str
    company: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_years: Optional[float] = None
    responsibilities: List[EvidenceDetail] = Field(default_factory=list)
    achievements: List[EvidenceDetail] = Field(default_factory=list)
    technologies: List[EvidenceDetail] = Field(default_factory=list)
    evidence: List[EvidenceDetail] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    candidate_id: Optional[str] = None
    candidate_name: Optional[str] = None
    summary: str
    professional_summary: Optional[str] = None
    experiences: List[ExperienceEntry] = Field(default_factory=list)
    skills: List[EvidenceDetail] = Field(default_factory=list)
    technologies: List[EvidenceDetail] = Field(default_factory=list)
    education: List[EvidenceDetail] = Field(default_factory=list)
    certifications: List[EvidenceDetail] = Field(default_factory=list)
    languages: List[EvidenceDetail] = Field(default_factory=list)
    total_years_experience: float = 0.0
    domain_experience: List[EvidenceDetail] = Field(default_factory=list)
    evidence: List[EvidenceDetail] = Field(default_factory=list)
    confidence: float = 0.0
    experience_years: Optional[int] = None
    matched_skills: List[str] = Field(default_factory=list)


class RequirementAssessment(BaseModel):
    requirement_id: str
    requirement_name: str
    mandatory: bool
    exclusionary: bool
    status: str
    raw_score: float
    max_score: float
    weighted_score: float
    evidence: List[EvidenceDetail] = Field(default_factory=list)
    gap_description: str
    confidence: float = 0.0


class FitAssessment(BaseModel):
    candidate_id: Optional[str] = None
    fit_percentage: float
    fit_level: str
    mandatory_fit: float
    desirable_fit: float
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    exclusionary_flags: List[str] = Field(default_factory=list)
    requirement_assessments: List[RequirementAssessment] = Field(default_factory=list)
    confidence: float = 0.0
    details: Optional[str] = None


class InterviewQuestion(BaseModel):
    question: str
    validates_requirement_id: str
    validates_requirement: str
    gap_type: str
    rationale: str
    expected_positive_evidence: str
    expected_warning_signals: List[str] = Field(default_factory=list)
    potential_fit_increase: float
    priority: int


class CandidateResult(BaseModel):
    candidate_id: str
    source_path: str
    name: str
    profile: Optional[CandidateProfile] = None
    fit_assessment: Optional[FitAssessment] = None
    interview_questions: List[InterviewQuestion] = Field(default_factory=list)
    retrieval_score: float = 0.0
    error: Optional[str] = None
    tokens: int = 0
    latency_ms: int = 0


class SupervisorResult(BaseModel):
    status: str
    decision: Optional[str] = None
    approved: Optional[bool] = None
    quality_score: Optional[float] = None
    dimension_scores: Optional[Dict[str, float]] = None
    issues: Optional[List[str]] = None
    flags: Optional[List[str]] = None
    modifications: Optional[Dict[str, Any]] = None
    final_result: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class TraceEntry(BaseModel):
    step: str
    agent: str
    status: str
    start_time: datetime
    end_time: datetime
    latency_ms: int
    message: Optional[str] = None


class FitAnalysisResult(BaseModel):
    analysis_id: str
    role: Dict[str, Any]
    candidates_analyzed: int
    ranking: List[Dict[str, Any]]
    supervisor_result: SupervisorResult
    traces: List[TraceEntry] = Field(default_factory=list)
    total_latency_ms: int
    total_tokens: int
    status: str
    errors: List[Dict[str, str]] = Field(default_factory=list)


class CandidateSource(BaseModel):
    candidate_id: str
    source_path: str
    name: str
    tokens: int = 0
    latency_ms: int = 0
