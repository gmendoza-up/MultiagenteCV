# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import CandidateResult, FitAssessment, InterviewQuestion

DEFAULT_RANKING_CONFIG = {
    "top_n": None,
    "fit_minimum": 0.0,
    "include_exclusionary_missing": False,
    "strengths_visible": 3,
    "gaps_visible": 3,
}

METHODOLOGICAL_WARNING = (
    "El ranking es una herramienta de apoyo a la decisión y no reemplaza la evaluación profesional ni la entrevista."
)


class RankingAgent:
    async def execute(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        await asyncio.sleep(0)
        job_description = payload.get("job_description") or {}
        candidate_fit_results = payload.get("candidate_fit_results") or []
        ranking_config = {**DEFAULT_RANKING_CONFIG, **(payload.get("ranking_config") or {})}

        normalized_candidates = [self._normalize_candidate(candidate, index) for index, candidate in enumerate(candidate_fit_results)]
        filtered_candidates = self._apply_filters(normalized_candidates, ranking_config)
        sorted_candidates = sorted(filtered_candidates, key=self._ranking_key)

        top_n = ranking_config.get("top_n")
        if top_n is not None:
            try:
                top_n_value = int(top_n)
            except (TypeError, ValueError):
                top_n_value = None
            if top_n_value is not None and top_n_value >= 0:
                sorted_candidates = sorted_candidates[:top_n_value]

        ranking = [self._build_ranking_item(candidate, rank + 1, ranking_config) for rank, candidate in enumerate(sorted_candidates)]
        comparison_summary = self._build_comparison_summary(sorted_candidates, job_description)

        result = {
            "role_id": str(job_description.get("role_id", "")),
            "role_title": str(job_description.get("role_title", job_description.get("role_summary", ""))),
            "total_candidates": len(ranking),
            "ranking": ranking,
            "comparison_summary": comparison_summary,
            "methodological_warning": METHODOLOGICAL_WARNING,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        tokens = 10 + len(ranking) * 2
        return result, tokens

    def _normalize_candidate(self, candidate: Any, index: int) -> Dict[str, Any]:
        if isinstance(candidate, dict):
            data = candidate.copy()
        elif hasattr(candidate, "model_dump"):
            data = candidate.model_dump()
        else:
            data = {k: getattr(candidate, k) for k in dir(candidate) if not k.startswith("__") and not callable(getattr(candidate, k))}

        fit_assessment = data.get("fit_assessment") or {}
        if hasattr(fit_assessment, "model_dump"):
            fit_assessment = fit_assessment.model_dump()

        data["fit_assessment"] = fit_assessment
        data["retrieval_score"] = float(data.get("retrieval_score", 0.0) or 0.0)
        data["original_index"] = index
        data["fit_percentage"] = float(fit_assessment.get("fit_percentage", 0.0) or 0.0)
        data["mandatory_fit"] = float(fit_assessment.get("mandatory_fit", 0.0) or 0.0)
        data["confidence"] = float(fit_assessment.get("confidence", 0.0) or 0.0)
        data["strengths"] = fit_assessment.get("strengths", []) or []
        data["gaps"] = fit_assessment.get("gaps", []) or []
        data["exclusionary_flags"] = fit_assessment.get("exclusionary_flags", []) or []
        data["interview_questions"] = data.get("interview_questions") or []
        data["requirement_assessments"] = fit_assessment.get("requirement_assessments", []) or []
        return data

    def _apply_filters(self, candidates: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        threshold = float(config.get("fit_minimum", 0.0) or 0.0)
        include_exclusionary = bool(config.get("include_exclusionary_missing", False))
        filtered: List[Dict[str, Any]] = []
        for candidate in candidates:
            if candidate["fit_percentage"] < threshold:
                continue
            if candidate["exclusionary_flags"] and not include_exclusionary:
                continue
            filtered.append(candidate)
        return filtered

    def _ranking_key(self, candidate: Dict[str, Any]) -> Tuple[Any, ...]:
        mandatory_requirements_met = sum(
            1
            for item in candidate["requirement_assessments"]
            if bool(item.get("mandatory", False)) and item.get("status") == "met"
        )
        return (
            -candidate["fit_percentage"],
            -candidate["mandatory_fit"],
            len(candidate["exclusionary_flags"]),
            -candidate["confidence"],
            -mandatory_requirements_met,
            -candidate["retrieval_score"],
            candidate["original_index"],
        )

    def _build_ranking_item(self, candidate: Dict[str, Any], rank: int, config: Dict[str, Any]) -> Dict[str, Any]:
        strengths_visible = int(config.get("strengths_visible", 3) or 3)
        gaps_visible = int(config.get("gaps_visible", 3) or 3)
        missing_mandatory_requirements = [
            item.get("requirement_name")
            for item in candidate["requirement_assessments"]
            if bool(item.get("mandatory", False)) and item.get("status") != "met"
        ]
        recommendation = self._recommendation(candidate, missing_mandatory_requirements)

        return {
            "rank": rank,
            "candidate_id": str(candidate.get("candidate_id", "")),
            "candidate_name": str(candidate.get("name", "")),
            "fit_percentage": candidate["fit_percentage"],
            "fit_level": str(candidate.get("fit_assessment", {}).get("fit_level", "")),
            "mandatory_fit": candidate["mandatory_fit"],
            "confidence": candidate["confidence"],
            "main_strengths": candidate["strengths"][:strengths_visible],
            "main_gaps": candidate["gaps"][:gaps_visible],
            "missing_mandatory_requirements": missing_mandatory_requirements,
            "exclusionary_flags": candidate["exclusionary_flags"],
            "interview_questions": [self._serialize_question(q) for q in candidate["interview_questions"]],
            "recommendation": recommendation,
        }

    def _serialize_question(self, question: Any) -> Dict[str, Any]:
        if hasattr(question, "model_dump"):
            return question.model_dump()
        if isinstance(question, dict):
            return question
        return {
            "question": getattr(question, "question", ""),
            "validates_requirement_id": getattr(question, "validates_requirement_id", ""),
            "validates_requirement": getattr(question, "validates_requirement", ""),
            "gap_type": getattr(question, "gap_type", ""),
            "rationale": getattr(question, "rationale", ""),
            "expected_positive_evidence": getattr(question, "expected_positive_evidence", ""),
            "expected_warning_signals": getattr(question, "expected_warning_signals", []),
            "potential_fit_increase": getattr(question, "potential_fit_increase", 0.0),
            "priority": getattr(question, "priority", 0),
        }

    def _recommendation(self, candidate: Dict[str, Any], missing_mandatory_requirements: List[str]) -> str:
        if candidate["exclusionary_flags"]:
            return "do_not_advance"
        if missing_mandatory_requirements:
            return "review"
        if candidate["fit_percentage"] >= 75.0:
            return "advance"
        if candidate["fit_percentage"] >= 50.0:
            return "review"
        return "do_not_advance"

    def _build_comparison_summary(self, candidates: List[Dict[str, Any]], job_description: Dict[str, Any]) -> Dict[str, Any]:
        table = [
            {
                "candidate_id": candidate.get("candidate_id", ""),
                "fit_percentage": candidate["fit_percentage"],
                "mandatory_fit": candidate["mandatory_fit"],
                "confidence": candidate["confidence"],
                "missing_mandatory_requirements": sum(
                    1
                    for item in candidate["requirement_assessments"]
                    if bool(item.get("mandatory", False)) and item.get("status") != "met"
                ),
                "exclusionary_flags": len(candidate["exclusionary_flags"]),
            }
            for candidate in candidates
        ]

        coverage = self._build_requirement_coverage(candidates, job_description)
        top_comparison = []
        if len(candidates) >= 2:
            first = candidates[0]
            second = candidates[1]
            top_comparison = [
                f"El candidato {first.get('candidate_id')} supera a {second.get('candidate_id')} en fit_percentage por {first['fit_percentage'] - second['fit_percentage']} puntos.",
                f"Diferencia de confidence: {round(first['confidence'] - second['confidence'], 1)}.",
            ]

        return {
            "candidate_table": table,
            "top_differences": top_comparison,
            "requirements_lowest_coverage": coverage.get("lowest", []),
            "requirements_highest_coverage": coverage.get("highest", []),
        }

    def _build_requirement_coverage(self, candidates: List[Dict[str, Any]], job_description: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        requirements = job_description.get("requirements") or []
        if not requirements:
            return {"lowest": [], "highest": []}

        coverage_stats: Dict[str, Dict[str, Any]] = {}
        total = len(candidates) or 1
        for requirement in requirements:
            req_id = requirement.get("requirement_id", requirement.get("name", ""))
            coverage_stats[req_id] = {
                "requirement_id": req_id,
                "requirement_name": requirement.get("name", ""),
                "met_count": 0,
                "coverage": 0.0,
            }

        for candidate in candidates:
            for assessment in candidate["requirement_assessments"]:
                req_id = assessment.get("requirement_id") or assessment.get("requirement_name")
                if req_id in coverage_stats and assessment.get("status") == "met":
                    coverage_stats[req_id]["met_count"] += 1

        for stats in coverage_stats.values():
            stats["coverage"] = round(stats["met_count"] / total * 100.0, 1)

        sorted_stats = sorted(coverage_stats.values(), key=lambda item: item["coverage"])
        lowest = sorted_stats[:3]
        highest = sorted_stats[-3:][::-1]
        return {"lowest": lowest, "highest": highest}
