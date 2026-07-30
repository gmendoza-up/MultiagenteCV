# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import math
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .models import CandidateProfile, EvidenceDetail, FitAssessment, RequirementAssessment


DEFAULT_SCORING_CONFIG = {
    "mandatory_requirements": 50.0,
    "relevant_experience": 20.0,
    "technologies_tools": 15.0,
    "education_certifications": 10.0,
    "desirable_requirements": 5.0,
    "exclusionary_penalty": 20.0,
}


class FitAssessmentAgent:
    async def execute(self, payload: Dict[str, Any]) -> Tuple[FitAssessment, int]:
        await asyncio.sleep(0)

        job_description = payload.get("job_description", {})
        profile = payload.get("candidate_profile")
        config = payload.get("scoring_config", {}) or {}

        if not isinstance(profile, CandidateProfile):
            raise ValueError("candidate_profile debe ser una instancia de CandidateProfile.")

        scoring_config = self._normalize_scoring_config(config)
        requirements = job_description.get("requirements") or []

        requirement_assessments: List[RequirementAssessment] = []
        mandatory_points = 0.0
        desirable_points = 0.0
        mandatory_max = 0.0
        desirable_max = 0.0
        strengths: List[str] = []
        gaps: List[str] = []
        exclusionary_flags: List[str] = []

        for req in requirements:
            assessment = self._assess_requirement(req, profile, scoring_config)
            requirement_assessments.append(assessment)

            if assessment.mandatory:
                mandatory_points += assessment.weighted_score
                mandatory_max += assessment.max_score
            else:
                desirable_points += assessment.weighted_score
                desirable_max += assessment.max_score

            if assessment.exclusionary and assessment.status != "met":
                exclusionary_flags.append(assessment.requirement_name)

            if assessment.status == "met" and assessment.weighted_score > 0:
                strengths.append(assessment.requirement_name)
            if assessment.status in {"not_evidenced", "partially_met", "contradicted"}:
                gaps.append(assessment.gap_description or assessment.requirement_name)

        mandatory_fit = self._normalize_ratio(mandatory_points, max(mandatory_max, 1.0))
        desirable_fit = self._normalize_ratio(desirable_points, max(desirable_max, 1.0))
        base_fit = self._normalize_ratio(mandatory_points + desirable_points, max(mandatory_max + desirable_max, 1.0))
        fit_percentage = self._apply_exclusionary_penalty(base_fit, exclusionary_flags, scoring_config)
        fit_level = self._fit_level(fit_percentage)

        confidence = self._estimate_confidence(requirement_assessments)

        assessment = FitAssessment(
            candidate_id=profile.candidate_id,
            fit_percentage=round(fit_percentage, 1),
            fit_level=fit_level,
            mandatory_fit=round(mandatory_fit, 1),
            desirable_fit=round(desirable_fit, 1),
            strengths=sorted(set(strengths)),
            gaps=sorted(set(gaps)),
            exclusionary_flags=sorted(set(exclusionary_flags)),
            requirement_assessments=requirement_assessments,
            confidence=round(confidence, 2),
            details="Evaluación determinística basada en evidencia y requisitos.",
        )

        tokens = 15 + len(requirement_assessments) * 3
        return assessment, tokens

    def _normalize_scoring_config(self, config: Dict[str, Any]) -> Dict[str, float]:
        scoring = {**DEFAULT_SCORING_CONFIG, **config}
        weights = [scoring.get("mandatory_requirements", 0.0), scoring.get("relevant_experience", 0.0), scoring.get("technologies_tools", 0.0), scoring.get("education_certifications", 0.0), scoring.get("desirable_requirements", 0.0)]
        total = sum(float(w) for w in weights)
        if total <= 0:
            raise ValueError("Las ponderaciones deben ser mayores que cero.")
        if abs(total - 100.0) > 1e-6:
            factor = 100.0 / total
            scoring["mandatory_requirements"] *= factor
            scoring["relevant_experience"] *= factor
            scoring["technologies_tools"] *= factor
            scoring["education_certifications"] *= factor
            scoring["desirable_requirements"] *= factor
        return scoring

    def _assess_requirement(self, requirement: Any, profile: CandidateProfile, scoring_config: Dict[str, float]) -> RequirementAssessment:
        req_id = requirement.get("requirement_id", "")
        name = requirement.get("name", "").strip()
        mandatory = bool(requirement.get("mandatory", False))
        exclusionary = bool(requirement.get("exclusionary", False))
        max_score = float(requirement.get("weight", 1.0))

        matched_evidence = self._find_evidence(name, profile)
        if matched_evidence:
            status = "met"
            raw_score = max_score
            confidence = max(e.confidence for e in matched_evidence)
        else:
            status = "not_evidenced"
            raw_score = 0.0
            confidence = 0.4

        if any(term in name.lower() for term in ["experiencia", "años", "experience"]):
            status, raw_score, confidence = self._assess_experience_requirement(requirement, profile, matched_evidence)

        weighted_score = raw_score * (max_score / max(1.0, max_score))
        evidence = matched_evidence
        gap_description = self._build_gap_description(requirement, status, matched_evidence)

        return RequirementAssessment(
            requirement_id=req_id,
            requirement_name=name,
            mandatory=mandatory,
            exclusionary=exclusionary,
            status=status,
            raw_score=round(raw_score, 2),
            max_score=round(max_score, 2),
            weighted_score=round(weighted_score, 2),
            evidence=evidence,
            gap_description=gap_description,
            confidence=round(confidence, 2),
        )

    def _find_evidence(self, text: str, profile: CandidateProfile) -> List[EvidenceDetail]:
        normalized = text.lower()
        evidence: List[EvidenceDetail] = []
        for item in profile.evidence + profile.technologies + profile.certifications + profile.skills + profile.education:
            if normalized and normalized in item.value.lower():
                evidence.append(item)
        return evidence

    def _assess_experience_requirement(self, requirement: Any, profile: CandidateProfile, evidence: List[EvidenceDetail]) -> Tuple[str, float, float]:
        minimum_years = requirement.get("minimum_years")
        if minimum_years is not None and profile.total_years_experience >= float(minimum_years):
            return "met", float(min(requirement.get("weight", 1.0), profile.total_years_experience)), 0.9
        if evidence:
            return "partially_met", float(requirement.get("weight", 0.5)), 0.6
        return "not_evidenced", 0.0, 0.4

    def _build_gap_description(self, requirement: Any, status: str, evidence: List[EvidenceDetail]) -> str:
        if status == "met":
            return ""
        if status == "partially_met":
            return f"El requisito '{requirement.get('name', '')}' tiene evidencia parcial pero no completa."
        return f"No se encontró evidencia clara para '{requirement.get('name', '')}'."

    def _normalize_ratio(self, numerator: float, denominator: float) -> float:
        if denominator <= 0:
            return 0.0
        return round(min(100.0, max(0.0, numerator / denominator * 100.0)), 1)

    def _apply_exclusionary_penalty(self, fit: float, exclusionary_flags: List[str], scoring_config: Dict[str, float]) -> float:
        if not exclusionary_flags:
            return fit
        penalty = float(scoring_config.get("exclusionary_penalty", 20.0))
        return round(max(0.0, fit - penalty), 1)

    def _fit_level(self, fit: float) -> str:
        if fit >= 75:
            return "high"
        if fit >= 45:
            return "medium"
        return "low"

    def _estimate_confidence(self, assessments: List[RequirementAssessment]) -> float:
        if not assessments:
            return 0.0
        weighted = sum(a.confidence for a in assessments) / len(assessments)
        return round(min(1.0, max(0.0, weighted)), 2)
