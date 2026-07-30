# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Tuple

from .models import SupervisorResult

SENSITIVE_TERMS = [
    "edad",
    "género",
    "genero",
    "nacionalidad",
    "dirección",
    "direccion",
    "estado civil",
    "fotografía",
    "foto",
    "religión",
    "salud",
    "casado",
    "hijo",
    "hijos",
    "matrimonio",
]

CRITICAL_FLAGS = {
    "sensitive_data": "Uso de datos sensibles detectado.",
    "ranking_inconsistency": "Ranking inconsistente con los resultados de fit.",
    "missing_analysis": "Uno o más candidatos carecen de análisis completo.",
}


class SupervisorAgent:
    async def execute(self, payload: Dict[str, Any]) -> Tuple[SupervisorResult, int]:
        await asyncio.sleep(0)
        job_description = payload.get("job_description") or {}
        candidate_profiles = payload.get("candidate_profiles") or []
        fit_results = payload.get("fit_results") or []
        ranking_result = payload.get("ranking_result") or {}
        traces = payload.get("traces") or []

        issues: List[str] = []
        flags: List[str] = []
        modifications: Dict[str, Any] = {}
        final_result: Dict[str, Any] = ranking_result.copy() if isinstance(ranking_result, dict) else {}

        evidence_score = self._assess_evidence(fit_results)
        coherence_score = self._assess_coherence(fit_results, ranking_result)
        quality_score = self._assess_quality(candidate_profiles, fit_results, ranking_result)
        safety_score = self._assess_safety(job_description, candidate_profiles, fit_results, ranking_result, traces)
        relevance_score = self._assess_relevance(fit_results, ranking_result)

        dimension_scores = {
            "evidence": round(evidence_score, 2),
            "coherence": round(coherence_score, 2),
            "quality": round(quality_score, 2),
            "safety": round(safety_score, 2),
            "relevance": round(relevance_score, 2),
        }
        aggregated_score = sum(dimension_scores.values()) / len(dimension_scores)
        decision = "approved"
        approved = True

        if safety_score < 0.6:
            decision = "rejected"
            approved = False
            flags.append("sensitive_data")
            issues.append("Se detectaron atributos sensibles en los datos del análisis.")

        if coherence_score < 0.6:
            if decision == "approved":
                decision = "modified_and_approved"
                approved = True
            flags.append("ranking_inconsistency")
            issues.append("El orden del ranking no coincide con los puntajes de fit.")
            corrected = self._correct_ranking(fit_results)
            final_result["ranking"] = corrected
            modifications["ranking_order"] = {
                "previous": [item.get("candidate_id") for item in ranking_result.get("ranking", [])],
                "updated": [item.get("candidate_id") for item in corrected],
                "reason": "Se ordenó el ranking según criterios determinísticos y no se cambió el fit.",
            }

        if quality_score < 0.6 and decision != "rejected":
            decision = "rejected"
            approved = False
            issues.append("La calidad del análisis es insuficiente debido a datos incompletos o preguntas faltantes.")

        if evidence_score < 0.5 and decision != "rejected":
            decision = "rejected"
            approved = False
            issues.append("No hay suficiente evidencia clara para respaldar los puntajes de fit.")

        if not final_result.get("methodological_warning"):
            final_result["methodological_warning"] = (
                "El ranking es una herramienta de apoyo a la decisión y no reemplaza la evaluación profesional ni la entrevista."
            )
            modifications["methodological_warning"] = {
                "previous": ranking_result.get("methodological_warning"),
                "updated": final_result["methodological_warning"],
                "reason": "Se agregó la advertencia metodológica faltante.",
            }
            if decision == "approved":
                decision = "modified_and_approved"

        if not candidate_profiles or not fit_results:
            issues.append("Faltan perfiles de candidatos o resultados de fit para la revisión.")
            if decision != "rejected":
                decision = "rejected"
                approved = False

        result = SupervisorResult(
            status=decision,
            reason=self._build_reason(decision, dimension_scores, issues),
            modifications=modifications or None,
            decision=decision,
            approved=approved,
            quality_score=round(aggregated_score, 2),
            dimension_scores=dimension_scores,
            issues=issues,
            flags=flags,
            final_result=final_result,
        )
        tokens = 18 + len(issues) * 2
        return result, tokens

    def _build_reason(self, decision: str, dimension_scores: Dict[str, float], issues: List[str]) -> str:
        if decision == "approved":
            return "El análisis cumple los criterios de evidencia, coherencia, calidad, seguridad y relevancia."
        if decision == "modified_and_approved":
            return "Se realizaron correcciones menores y el análisis sigue siendo aprobado bajo supervisión."
        return "El análisis no cumple los criterios mínimos y debe ser rechazado."

    def _assess_evidence(self, fit_results: List[Any]) -> float:
        if not fit_results:
            return 0.0
        score = 0.0
        for fit in fit_results:
            assessments = fit.get("requirement_assessments", []) or []
            if not assessments:
                continue
            matched = sum(1 for item in assessments if item.get("status") in {"met", "partially_met"} and item.get("evidence"))
            score += min(1.0, matched / len(assessments))
        return score / len(fit_results)

    def _assess_coherence(self, fit_results: List[Any], ranking_result: Dict[str, Any]) -> float:
        ranking = ranking_result.get("ranking") or []
        if not ranking or not fit_results:
            return 0.0
        expected_order = sorted(
            fit_results,
            key=lambda item: (
                -float(item.get("fit_percentage", 0.0) or 0.0),
                -float(item.get("mandatory_fit", 0.0) or 0.0),
                len(item.get("exclusionary_flags", []) or []),
                -float(item.get("confidence", 0.0) or 0.0),
                -sum(1 for req in (item.get("requirement_assessments") or []) if req.get("mandatory") and req.get("status") == "met"),
                -float(item.get("retrieval_score", 0.0) or 0.0),
            )
        )
        expected_ids = [item.get("candidate_id") for item in expected_order]
        actual_ids = [item.get("candidate_id") for item in ranking]
        if not actual_ids:
            return 0.0
        matches = sum(1 for expected, actual in zip(expected_ids, actual_ids) if expected == actual)
        return matches / max(len(actual_ids), len(expected_ids))

    def _assess_quality(self, candidate_profiles: List[Any], fit_results: List[Any], ranking_result: Dict[str, Any]) -> float:
        if not candidate_profiles or not fit_results:
            return 0.0
        profile_ids = {item.get("candidate_id") for item in candidate_profiles if item.get("candidate_id")}
        fit_ids = {item.get("candidate_id") for item in fit_results if item.get("candidate_id")}
        ranking_ids = {item.get("candidate_id") for item in (ranking_result.get("ranking") or []) if item.get("candidate_id")}
        if profile_ids != fit_ids or fit_ids != ranking_ids:
            return 0.0

        question_quality = 0.0
        for profile in candidate_profiles:
            questions = profile.get("interview_questions") or []
            if len(questions) == 5:
                question_quality += 1.0
        return question_quality / len(candidate_profiles)

    def _assess_safety(self, job_description: Dict[str, Any], candidate_profiles: List[Any], fit_results: List[Any], ranking_result: Dict[str, Any], traces: List[Any]) -> float:
        texts = []
        texts.append(self._gather_text(job_description))
        texts.extend(self._gather_text(item) for item in candidate_profiles)
        texts.extend(self._gather_text(item) for item in fit_results)
        texts.append(self._gather_text(ranking_result))
        texts.extend(self._gather_text(item) for item in traces)
        if any(self._contains_sensitive(text) for text in texts):
            return 0.0
        return 1.0

    def _assess_relevance(self, fit_results: List[Any], ranking_result: Dict[str, Any]) -> float:
        if not fit_results or not ranking_result.get("ranking"):
            return 0.0
        if ranking_result.get("total_candidates") == len(ranking_result.get("ranking", [])):
            return 1.0
        return 0.8

    def _contains_sensitive(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in SENSITIVE_TERMS)

    def _gather_text(self, item: Any) -> str:
        if item is None:
            return ""
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return " ".join(self._gather_text(value) for value in item.values())
        if isinstance(item, list):
            return " ".join(self._gather_text(value) for value in item)
        return str(item)

    def _correct_ranking(self, fit_results: List[Any]) -> List[Dict[str, Any]]:
        ordered = sorted(
            fit_results,
            key=lambda item: (
                -float(item.get("fit_percentage", 0.0) or 0.0),
                -float(item.get("mandatory_fit", 0.0) or 0.0),
                len(item.get("exclusionary_flags", []) or []),
                -float(item.get("confidence", 0.0) or 0.0),
                -sum(1 for req in (item.get("requirement_assessments") or []) if req.get("mandatory") and req.get("status") == "met"),
                -float(item.get("retrieval_score", 0.0) or 0.0),
            )
        )
        return [
            {
                "candidate_id": item.get("candidate_id"),
                "fit_percentage": item.get("fit_percentage"),
                "mandatory_fit": item.get("mandatory_fit"),
                "confidence": item.get("confidence"),
                "requirement_assessments": item.get("requirement_assessments", []),
                "exclusionary_flags": item.get("exclusionary_flags", []),
            }
            for item in ordered
        ]
