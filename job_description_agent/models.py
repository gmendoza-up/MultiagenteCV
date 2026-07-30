# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator


class RequirementModel(BaseModel):
    requirement_id: str
    name: str
    category: str
    mandatory: bool
    exclusionary: bool
    weight: float
    minimum_level: str
    minimum_years: Optional[float] = None
    synonyms: List[str] = Field(default_factory=list)
    source_text: str
    confidence: float
    ambiguous: bool


class JobDescriptionStructured(BaseModel):
    role_id: Optional[str]
    role_title: str
    role_summary: str
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[RequirementModel] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    weights: Dict[str, float] = Field(default_factory=dict)
    ambiguities: List[str] = Field(default_factory=list)
    clarification_questions: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class WeightConfig(BaseModel):
    weights: Dict[str, float] = Field(default_factory=dict)

    @root_validator(pre=True)
    def ensure_sum_100(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        raw_weights = values.get("weights", {}) or {}
        if not raw_weights:
            return {"weights": raw_weights}
        total = sum(float(v) for v in raw_weights.values())
        if abs(total - 100.0) > 1e-6:
            raise ValueError("La suma de las ponderaciones debe ser 100.")
        return values


def normalize_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
