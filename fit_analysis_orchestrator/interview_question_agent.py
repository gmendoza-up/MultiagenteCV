# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import re
from typing import List, Optional, Tuple

from .models import CandidateProfile, InterviewQuestion, RoleDescriptor, EvidenceDetail

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

REQUIRED_KEYWORD_PATTERNS = [
    "python",
    "sql",
    "comunicación",
    "comunicacion",
    "análisis de datos",
    "analisis de datos",
    "gestión de proyectos",
    "gestion de proyectos",
    "stakeholders",
    "equipo",
    "liderazgo",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
]

QUESTION_TEMPLATES = {
    "technical": (
        "Describe un proyecto real donde aplicaste {topic} para resolver un problema relevante del negocio.",
        "Verificar la experiencia práctica y su impacto sobre los resultados.",
        [
            "Respuestas demasiado generales o teóricas sin ejemplos de implementación.",
            "No menciona resultados concretos ni métricas.",
        ],
    ),
    "communication_stakeholders": (
        "Cuéntame cómo te aseguraste de que tu equipo y los stakeholders entendieran los resultados técnicos de un proyecto.",
        "Confirmar la capacidad de comunicación efectiva con distintos públicos.",
        [
            "Describe solo carga de trabajo sin contexto de comunicación.",
            "No indica cómo adaptó el mensaje a distintos interlocutores.",
        ],
    ),
    "communication_clarity": (
        "Describe cómo te aseguras de que la comunicación técnica sea clara y efectiva para diferentes audiencias.",
        "Evaluar claridad de comunicación y adaptación de mensaje.",
        [
            "Demasiado enfoque en jerga técnica sin explicar el impacto.",
            "No menciona adaptación del mensaje según el público.",
        ],
    ),
    "experience": (
        "Explícame un desafío significativo que enfrentaste en un proyecto y cómo lo solucionaste empleando tus habilidades técnicas.",
        "Evaluar resolución de problemas y profundidad técnica.",
        [
            "No justifica las decisiones técnicas tomadas.",
            "Omisión de resultados medibles o consecuencias.",
        ],
    ),
    "results": (
        "Describe un resultado cuantificable que obtuviste en un proyecto y qué acciones tuyas lo hicieron posible.",
        "Corroborar el enfoque en resultados y el aporte personal.",
        [
            "No aporta cifras o mejoras específicas.",
            "Se enfoca en tareas en lugar del impacto.",
        ],
    ),
    "adaptability": (
        "¿Cómo aprendiste una tecnología o herramienta nueva cuando un proyecto lo requería y cómo la aplicaste después?",
        "Medir capacidad de aprendizaje rápido y adaptación técnica.",
        [
            "Se limita a decir que estudió sin dar ejemplos prácticos.",
            "No menciona aplicación real en un proyecto.",
        ],
    ),
}


class InterviewQuestionAgent:
    async def execute(self, profile: CandidateProfile, role: RoleDescriptor) -> Tuple[List[InterviewQuestion], int]:
        await asyncio.sleep(0)

        requirements = self._extract_requirements(role.description_text)
        evidence_terms = self._collect_profile_terms(profile)
        missing_terms = self._find_missing_terms(requirements, evidence_terms)
        validated_requirements = self._rank_requirements(requirements, missing_terms)
        questions: List[InterviewQuestion] = []

        for index, requirement in enumerate(validated_requirements[:5]):
            question = self._build_question(requirement, profile, role, index + 1)
            questions.append(question)

        while len(questions) < 5:
            fallback = self._build_fallback_question(profile, role, len(questions) + 1)
            questions.append(fallback)

        tokens = 12 + len(questions) * 2
        return questions, tokens

    def _extract_requirements(self, description: str) -> List[str]:
        segments = re.split(r"[\n\r;\.]+", description or "")
        requirements: List[str] = []
        for segment in segments:
            text = segment.strip()
            if not text:
                continue
            if any(keyword in text.lower() for keyword in REQUIRED_KEYWORD_PATTERNS):
                subtasks = re.split(r"\s*(?:,| y | e )\s*", text)
                for subtask in subtasks:
                    normalized = subtask.strip().lower()
                    if normalized and any(keyword in normalized for keyword in REQUIRED_KEYWORD_PATTERNS):
                        requirements.append(subtask.strip())

        if not requirements:
            for keyword in REQUIRED_KEYWORD_PATTERNS:
                if keyword in description.lower():
                    requirements.append(keyword)
        if not requirements and description.strip():
            requirements = [description.strip()]
        unique_requirements = []
        seen = set()
        for req in requirements:
            key = req.lower()
            if key not in seen:
                seen.add(key)
                unique_requirements.append(req)
        return unique_requirements[:8]

    def _collect_profile_terms(self, profile: CandidateProfile) -> List[str]:
        terms: List[str] = []
        for item in profile.technologies + profile.skills + profile.certifications + profile.education + profile.domain_experience:
            value = (item.value or "").strip().lower()
            if value:
                terms.append(value)
        if profile.summary:
            terms.extend(re.findall(r"\w+", profile.summary.lower()))
        return sorted(set(terms))

    def _find_missing_terms(self, requirements: List[str], profile_terms: List[str]) -> List[str]:
        missing: List[str] = []
        term_set = {term.lower() for term in profile_terms}
        for requirement in requirements:
            normalized = requirement.lower()
            if "python" in normalized and "python" not in term_set:
                missing.append(requirement)
                continue
            if "sql" in normalized and "sql" not in term_set:
                missing.append(requirement)
                continue
            if "stakeholders" in normalized and "stakeholders" not in term_set:
                missing.append(requirement)
                continue
            if any(keyword in normalized for keyword in ["comunicación", "comunicacion"]) and not any(keyword in term_set for keyword in ["comunicación", "comunicacion", "communication"]):
                missing.append(requirement)
                continue
            if any(keyword in normalized for keyword in ["aws", "docker", "kubernetes", "gcp", "azure"]) and not any(keyword in term_set for keyword in ["aws", "docker", "kubernetes", "gcp", "azure"]):
                missing.append(requirement)
                continue
            if any(keyword in normalized for keyword in ["experiencia", "years", "años", "experience"]) and not any(keyword in term_set for keyword in ["experiencia", "experience", "años", "years"]):
                missing.append(requirement)
                continue
        return missing

    def _rank_requirements(self, requirements: List[str], missing_requirements: List[str]) -> List[str]:
        if not missing_requirements:
            return requirements[:5]

        def priority(req: str) -> int:
            lower = req.lower()
            if "python" in lower:
                return 1
            if "sql" in lower:
                return 2
            if "stakeholders" in lower:
                return 3
            if any(k in lower for k in ["comunicación", "comunicacion"]):
                return 4
            if any(k in lower for k in ["experiencia", "años", "experience"]):
                return 5
            return 6

        ordered_missing = sorted(missing_requirements, key=priority)
        remaining = [req for req in requirements if req not in missing_requirements]
        return (ordered_missing + remaining)[:5]

    def _build_question(self, requirement: str, profile: CandidateProfile, role: RoleDescriptor, priority: int) -> InterviewQuestion:
        normalized = requirement.lower()
        if "python" in normalized or "sql" in normalized or "aws" in normalized or "docker" in normalized or "kubernetes" in normalized:
            template_key = "technical"
            gap_type = "technical_depth"
        elif "stakeholders" in normalized:
            template_key = "communication_stakeholders"
            gap_type = "communication"
        elif "comunicación" in normalized or "comunicacion" in normalized:
            template_key = "communication_clarity"
            gap_type = "communication"
        elif "experiencia" in normalized or "años" in normalized or "experience" in normalized:
            template_key = "experience"
            gap_type = "experience_gap"
        elif "liderazgo" in normalized or "equipo" in normalized or "gestión" in normalized or "gestion" in normalized:
            template_key = "adaptability"
            gap_type = "leadership"
        else:
            template_key = "results"
            gap_type = "results_orientation"

        question_text, rationale, warning_signals = QUESTION_TEMPLATES[template_key]
        topic = self._detect_topic(requirement, profile)
        if "{topic}" in question_text:
            question = question_text.format(topic=topic)
        else:
            question = question_text

        if self._contains_sensitive(question):
            question = self._sanitize_question(question)

        potential_increase = self._estimate_potential_increase(gap_type, priority)

        return InterviewQuestion(
            question=question,
            validates_requirement_id=self._sanitize_requirement_id(requirement),
            validates_requirement=requirement,
            gap_type=gap_type,
            rationale=rationale,
            expected_positive_evidence=f"Busca evidencia práctica de {topic} y resultados concretos.",
            expected_warning_signals=warning_signals,
            potential_fit_increase=potential_increase,
            priority=priority,
        )

    def _detect_topic(self, requirement: str, profile: CandidateProfile) -> str:
        normalized = requirement.lower()
        for token in ["python", "sql", "comunicación", "comunicacion", "aws", "azure", "gcp", "docker", "kubernetes"]:
            if token in normalized:
                return token.upper() if token.isupper() else token
        if profile.technologies:
            return profile.technologies[0].value
        if profile.skills:
            return profile.skills[0].value
        return "esa competencia"

    def _contains_sensitive(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in SENSITIVE_TERMS)

    def _sanitize_question(self, text: str) -> str:
        return re.sub(r"\b(edad|género|genero|nacionalidad|dirección|direccion|estado civil|fotografía|foto|religión|salud|casado|hijo|hijos|matrimonio)\b", "competencia", text, flags=re.IGNORECASE)

    def _sanitize_requirement_id(self, requirement: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9]+", "-", requirement.lower()).strip("-")
        return sanitized[:40] or "requirement"

    def _estimate_potential_increase(self, gap_type: str, priority: int) -> float:
        base = {
            "technical_depth": 12.0,
            "communication": 10.0,
            "experience_gap": 11.0,
            "leadership": 8.0,
            "results_orientation": 7.0,
        }.get(gap_type, 8.0)
        return round(max(3.0, base - (priority - 1) * 1.5), 1)

    def _build_fallback_question(self, profile: CandidateProfile, role: RoleDescriptor, priority: int) -> InterviewQuestion:
        if profile.total_years_experience and profile.total_years_experience < 3:
            gap_type = "experience_gap"
            question = (
                "Describe un desafío técnico reciente en el que tuviste que aprender rápido y cómo lo resolviste."
            )
            rationale = "Investiga la capacidad de aprendizaje y la experiencia práctica en proyectos."
            warning_signals = [
                "Respuestas poco concretas sobre el proyecto.",
                "No menciona resultados o decisiones técnicas claras.",
            ]
        else:
            gap_type = "results_orientation"
            question = (
                "Relata un proyecto en el que contribuiste con resultados medibles y cómo evalúas tu impacto."
            )
            rationale = "Busca detalles sobre el aporte directo al negocio y el enfoque en resultados."
            warning_signals = [
                "No explica el impacto real del proyecto.",
                "Se queda en descripciones generales de tareas.",
            ]

        potential_increase = self._estimate_potential_increase(gap_type, priority)
        return InterviewQuestion(
            question=question,
            validates_requirement_id=f"fallback-{priority}",
            validates_requirement=role.description_text.strip()[:80] if role.description_text else "Requisito general",
            gap_type=gap_type,
            rationale=rationale,
            expected_positive_evidence="Busca detalles sobre resultados reales y el rol del candidato.",
            expected_warning_signals=warning_signals,
            potential_fit_increase=potential_increase,
            priority=priority,
        )
