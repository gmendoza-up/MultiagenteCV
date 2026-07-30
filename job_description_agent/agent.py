# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import JobDescriptionStructured, RequirementModel, WeightConfig

LOGGER = logging.getLogger("JobDescriptionAgent")

DEFAULT_WEIGHTS = {
    "mandatory_requirements": 50.0,
    "relevant_experience": 20.0,
    "technologies_tools": 15.0,
    "education_certifications": 10.0,
    "desirable_requirements": 5.0,
}


def configure_logging() -> None:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)


def extract_lines(text: str) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines


def find_title(lines: List[str]) -> str:
    if not lines:
        return ""
    return lines[0]


def build_summary(text: str) -> str:
    text = text.strip()
    if len(text) <= 280:
        return text
    return text.replace("\n", " ")[:280].strip()


def is_requirement_line(line: str) -> bool:
    return bool(re.search(r"(requisitos|required|must|debe|deben|condiciones|excluyente|excluye|preferible|deseable)", line, re.IGNORECASE))


def detect_experience(line: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:años|años de|years|yrs|anos)", line, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_list_from_block(text: str) -> List[str]:
    items = re.split(r"\n|;|\*|\u2022|-|–", text)
    return [item.strip() for item in items if item.strip()]


def clean_requirement_name(text: str) -> str:
    text = re.sub(r"^(?:-\s*)?", "", text)
    return text.strip()


@dataclass
class JobDescriptionAgent:
    config_weights: Dict[str, float] = None

    def __post_init__(self) -> None:
        self.config_weights = self.config_weights or DEFAULT_WEIGHTS
        try:
            WeightConfig(weights=self.config_weights)
        except ValueError as exc:
            raise

    async def execute(self, payload: Dict[str, Any]) -> JobDescriptionStructured:
        configure_logging()
        LOGGER.info("Iniciando análisis de descriptivo de cargo")

        role_id = payload.get("role_id")
        raw_text = payload.get("role_description", "")
        if not raw_text.strip():
            raise ValueError("El campo 'role_description' es obligatorio.")

        lines = extract_lines(raw_text)
        role_title = find_title(lines)
        role_summary = build_summary(raw_text)

        responsibilities: List[str] = []
        requirements: List[RequirementModel] = []
        technologies: List[str] = []
        tools: List[str] = []
        education: List[str] = []
        certifications: List[str] = []
        languages: List[str] = []
        ambiguities: List[str] = []
        clarification_questions: List[str] = []

        normalized_seen: Dict[str, RequirementModel] = {}

        blocks = re.split(r"\n\n+", raw_text)
        for block in blocks:
            lower = block.lower()
            if re.search(r"responsa|responsabili|tareas|funciones", lower):
                responsibilities.extend(extract_list_from_block(block))
            if re.search(r"tecnolog|tech|python|java|javascript|sql|spark|aws|azure|gcp", lower):
                technologies.extend(re.findall(r"\b[A-Za-z0-9#+]+\b", block))
            if re.search(r"herramienta|tool|jira|confluence|git|docker|kubernetes|linux|excel", lower):
                tools.extend(re.findall(r"\b[A-Za-z0-9#+]+\b", block))
            if re.search(r"formaci|educaci|grado|licenciatura|título|titulaci|bachiller|magíster|doctorado", lower):
                education.extend(extract_list_from_block(block))
            if re.search(r"certificaci|certificación|certified|certified|cisco|aws|azure|gcp", lower):
                certifications.extend(extract_list_from_block(block))
            if re.search(r"idiom|inglés|english|español|espanol|francés|frances|portugués|portugues", lower):
                languages.extend(re.findall(r"\b[A-Za-záéíóúüñ]+\b", block))

            if is_requirement_line(block):
                mandatory_block = bool(re.search(r"\b(obligatorio|obligatoria|obligatorios|requisitos obligatorios|requisitos excluyentes|requisitos excluyentes)\b", lower))
                desirable_block = bool(re.search(r"\b(deseable|preferible|requisitos deseables|requisitos deseables)\b", lower))
                for item in extract_list_from_block(block):
                    if not item:
                        continue
                    if re.match(r"^(requisitos|requisitos obligatorios|requisitos deseables|responsabilidades|tareas|funciones)\b", item.strip().lower()):
                        continue
                    requirement = self._build_requirement(item, forced_mandatory=mandatory_block, block_desirable=desirable_block)
                    key = requirement.name.lower()
                    if key in normalized_seen:
                        existing = normalized_seen[key]
                        existing.synonyms.append(requirement.source_text)
                        existing.confidence = max(existing.confidence, requirement.confidence)
                        existing.weight = max(existing.weight, requirement.weight)
                        existing.ambiguous = existing.ambiguous or requirement.ambiguous
                    else:
                        normalized_seen[key] = requirement

        if not responsibilities:
            responsibilities = extract_list_from_block(raw_text)

        technologies = sorted(set(technologies))
        tools = sorted(set(tools))
        education = sorted(set(education))
        certifications = sorted(set(certifications))
        languages = sorted(set(languages))

        if not normalized_seen:
            clarifications = [
                "¿Cuál es el nivel mínimo de experiencia esperado?",
                "¿Qué certificaciones son obligatorias para este rol?",
            ]
            clarification_questions.extend(clarifications)

        if not any(detect_experience(line) is not None for line in extract_lines(raw_text)):
            clarification_questions.append(
                "¿Cuántos años mínimos de experiencia se requieren para este puesto?"
            )

        final_requirements = list(normalized_seen.values())
        total_weight = sum(req.weight for req in final_requirements)
        expected = sum(self.config_weights.values())
        if abs(total_weight - expected) > 0.1 and final_requirements:
            scale = expected / total_weight if total_weight else 1.0
            for req in final_requirements:
                req.weight = round(req.weight * scale, 2)

        confidence = 1.0 - min(0.2, len(ambiguities) * 0.05 + len(clarification_questions) * 0.05)

        return JobDescriptionStructured(
            role_id=role_id,
            role_title=role_title,
            role_summary=role_summary,
            responsibilities=[r for r in responsibilities if r],
            requirements=final_requirements,
            technologies=technologies,
            tools=tools,
            education=education,
            certifications=certifications,
            languages=languages,
            weights=self.config_weights,
            ambiguities=ambiguities,
            clarification_questions=clarification_questions,
            confidence=round(confidence, 2),
        )

    def _build_requirement(self, text: str, forced_mandatory: bool = False, block_desirable: bool = False) -> RequirementModel:
        text = clean_requirement_name(text)
        lower = text.lower()
        mandatory = forced_mandatory or bool(re.search(r"\b(must|debe|obligatorio|obligatoria|obligatorios|requerido|requerida|es obligatorio)\b", lower))
        if block_desirable and not mandatory:
            mandatory = False
        exclusionary = bool(re.search(r"\b(exclu|no se acept|sin experiencia en|no requerido|excepto)\b", lower))
        ambiguous = bool(re.search(r"\b(posiblemente|puede ser|idealmente|preferible|de preferencia|a convenir)\b", lower))
        years = detect_experience(text)
        category = self._detect_category(lower)
        weight = self._initial_weight(category, mandatory, block_desirable)
        confidence = 0.8 if ambiguous else 0.95

        if block_desirable and not mandatory:
            weight = max(1.0, weight * 0.5)

        return RequirementModel(
            requirement_id=str(uuid.uuid4()),
            name=text,
            category=category,
            mandatory=mandatory,
            exclusionary=exclusionary,
            weight=weight,
            minimum_level="" if not years else "Intermediate",
            minimum_years=years,
            synonyms=[],
            source_text=text,
            confidence=confidence,
            ambiguous=ambiguous,
        )

    def _detect_category(self, lower: str) -> str:
        if re.search(r"(certificaci|certification|certified)", lower):
            return "certification"
        if re.search(r"(grado|licenciatura|título|titulación|bachiller|magíster|doctorado)", lower):
            return "education"
        if re.search(r"(idiom|inglés|english|español|espanol|francés|frances|portugués|portugues)", lower):
            return "language"
        if re.search(r"(python|java|sql|aws|azure|gcp|docker|kubernetes|spark|linux)", lower):
            return "technology"
        if re.search(r"(herramienta|tool|jira|confluence|git|excel)", lower):
            return "tool"
        if re.search(r"(competencias?|habilidades?)", lower):
            return "competency"
        if re.search(r"(responsab|tarea|funcion)", lower):
            return "responsibility"
        return "requirement"

    def _initial_weight(self, category: str, mandatory: bool, block_desirable: bool = False) -> float:
        if category == "certification":
            return 5.0
        if category == "education":
            return 5.0
        if category == "language":
            return 3.0
        if category == "technology":
            return 10.0
        if category == "tool":
            return 5.0
        if category == "competency":
            return 8.0
        base_weight = 2.0 if not mandatory else 7.0
        if block_desirable:
            return max(1.0, base_weight * 0.5)
        return base_weight


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JobDescriptionAgent")
    parser.add_argument("--payload", required=True, help="JSON con role_id y role_description")
    parser.add_argument("--weights", default="{}", help="JSON con las ponderaciones iniciales que suman 100")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    payload = json.loads(args.payload)
    weights = json.loads(args.weights) if args.weights else DEFAULT_WEIGHTS

    agent = JobDescriptionAgent(config_weights=weights)
    result = asyncio.run(agent.execute(payload))
    print(result.model_dump_json(indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
