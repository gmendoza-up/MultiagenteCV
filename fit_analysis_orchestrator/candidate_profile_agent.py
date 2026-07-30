# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .models import CandidateProfile, CandidateSource, EvidenceDetail, ExperienceEntry, WeightConfig


DATE_PATTERN = re.compile(
    r"(?P<month>enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\s*(?P<year>\d{4})",
    re.IGNORECASE,
)

TECHNOLOGY_PATTERN = re.compile(
    r"\b(Python|SQL|Java|Spark|Hadoop|AWS|Azure|GCP|Docker|Kubernetes|TensorFlow|PyTorch|Scala|R|Tableau|Power BI|SageMaker)\b",
    re.IGNORECASE,
)

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


class CandidateProfileAgent:
    async def execute(self, payload: Dict[str, Any]) -> Tuple[CandidateProfile, int]:
        await asyncio.sleep(0)

        candidate_id = payload.get("candidate_id")
        cv_chunks = payload.get("cv_chunks") or []
        source_file = payload.get("source_file", "")

        evidence: List[EvidenceDetail] = []
        experiences: List[ExperienceEntry] = []
        skills: List[EvidenceDetail] = []
        technologies: List[EvidenceDetail] = []
        education: List[EvidenceDetail] = []
        certifications: List[EvidenceDetail] = []
        languages: List[EvidenceDetail] = []
        domain_experience: List[EvidenceDetail] = []

        candidate_name = self._extract_candidate_name(cv_chunks, candidate_id)
        summary_text = self._build_professional_summary(cv_chunks)

        for chunk in cv_chunks:
            text = self._text(chunk.get("content"))
            if not text:
                continue
            if self._contains_sensitive(text):
                continue

            self._collect_education(chunk, education)
            self._collect_certifications(chunk, certifications)
            self._collect_languages(chunk, languages)
            self._collect_technologies(chunk, technologies)
            self._collect_skills(chunk, skills)
            self._collect_domain_experience(chunk, domain_experience)
            self._collect_experience_entry(chunk, experiences)

            evidence.append(
                EvidenceDetail(
                    value=text[:120],
                    evidence_text=text,
                    source_file=chunk.get("source_file", source_file),
                    page=int(chunk.get("page", 0) or 0),
                    section=chunk.get("section", ""),
                    evidence_type="explicit" if self._is_explicit(text) else "indirect",
                    confidence=0.9 if self._is_explicit(text) else 0.6,
                )
            )

        experiences = self._consolidate_experiences(experiences)
        total_years = self._calculate_total_experience(experiences)
        technology_years = self._estimate_years_by_technology(technologies)

        profile = CandidateProfile(
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            summary=summary_text,
            professional_summary=summary_text,
            experiences=experiences,
            skills=skills,
            technologies=technologies,
            education=education,
            certifications=certifications,
            languages=languages,
            total_years_experience=total_years,
            domain_experience=domain_experience,
            evidence=evidence,
            confidence=self._estimate_confidence(experiences, evidence),
        )

        tokens = 20 + len(evidence)
        return profile, tokens

    def _text(self, value: Any) -> str:
        if not value:
            return ""
        return str(value).strip()

    def _extract_candidate_name(self, chunks: List[Dict[str, Any]], candidate_id: Optional[str]) -> str:
        for chunk in chunks:
            content = self._text(chunk.get("content"))
            if not content:
                continue
            match = re.search(r"^Nombre\s*[:\-]\s*(.+)$", content, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        if candidate_id:
            return candidate_id.replace("_", " ")
        return ""

    def _build_professional_summary(self, chunks: List[Dict[str, Any]]) -> str:
        summaries: List[str] = []
        for chunk in chunks:
            text = self._text(chunk.get("content"))
            if not text:
                continue
            if len(text.split()) <= 40 and "experiencia" in text.lower():
                summaries.append(text)
        if summaries:
            return " ".join(summaries[:2])
        if chunks:
            return self._text(chunks[0].get("content", ""))[:320]
        return ""

    def _contains_sensitive(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in SENSITIVE_TERMS)

    def _is_explicit(self, text: str) -> bool:
        return bool(
            re.search(
                r"\b(experiencia|trabaj|lider|gestion|responsabilidad|responsabilidades|logro|certificaci|titulo|habilidad)\b",
                text,
                re.IGNORECASE,
            )
        )

    def _collect_education(self, chunk: Dict[str, Any], education: List[EvidenceDetail]) -> None:
        text = self._text(chunk.get("content", ""))
        if re.search(r"(grado|licenciatura|bachiller|magíster|doctorado|universidad|carrera|título|titulación)", text, re.IGNORECASE):
            education.append(self._build_evidence(chunk, text, "explicit", 0.8))

    def _collect_certifications(self, chunk: Dict[str, Any], certifications: List[EvidenceDetail]) -> None:
        text = self._text(chunk.get("content", ""))
        if re.search(r"(certificaci|certificado|certified|AWS Certified|Cisco|Microsoft Certified)", text, re.IGNORECASE):
            certifications.append(self._build_evidence(chunk, text, "explicit", 0.85))

    def _collect_languages(self, chunk: Dict[str, Any], languages: List[EvidenceDetail]) -> None:
        text = self._text(chunk.get("content", ""))
        if re.search(r"\b(inglés|ingles|español|spanish|english|portugués|portugues|francés|frances)\b", text, re.IGNORECASE):
            languages.append(self._build_evidence(chunk, text, "explicit", 0.8))

    def _collect_technologies(self, chunk: Dict[str, Any], technologies: List[EvidenceDetail]) -> None:
        text = self._text(chunk.get("content", ""))
        for match in TECHNOLOGY_PATTERN.finditer(text):
            technologies.append(
                self._build_evidence(chunk, match.group(0), "explicit", 0.9)
            )

    def _collect_skills(self, chunk: Dict[str, Any], skills: List[EvidenceDetail]) -> None:
        text = self._text(chunk.get("content", ""))
        if re.search(r"\b(gestión|liderazgo|comunicación|análisis|resolución|planificación|estrategia)\b", text, re.IGNORECASE):
            skills.append(self._build_evidence(chunk, text, "indirect", 0.7))

    def _collect_domain_experience(self, chunk: Dict[str, Any], domain_experience: List[EvidenceDetail]) -> None:
        text = self._text(chunk.get("content", ""))
        if re.search(r"\b(finanzas|banca|salud|educación|retail|seguros|telecomunicaciones|energía)\b", text, re.IGNORECASE):
            domain_experience.append(self._build_evidence(chunk, text, "explicit", 0.8))

    def _collect_experience_entry(self, chunk: Dict[str, Any], experiences: List[ExperienceEntry]) -> None:
        text = self._text(chunk.get("content", ""))
        section = self._text(chunk.get("section", "Experiencia"))
        if re.search(r"\b(experiencia|trabaj|cargo|puesto|empresa|empresa:|responsabilidad|logro)\b", text, re.IGNORECASE):
            start_date, end_date = self._parse_dates(text)
            entry = ExperienceEntry(
                title=self._extract_title(text),
                company=self._extract_company(text),
                start_date=start_date,
                end_date=end_date,
                duration_years=self._estimate_duration(start_date, end_date),
                responsibilities=[self._build_evidence(chunk, text, "explicit", 0.8)],
                achievements=[self._build_evidence(chunk, text, "indirect", 0.6)] if re.search(r"\b(logro|resultado|mejor|aumento|reducción)\b", text, re.IGNORECASE) else [],
                technologies=[self._build_evidence(chunk, m.group(0), "explicit", 0.9) for m in TECHNOLOGY_PATTERN.finditer(text)],
                evidence=[self._build_evidence(chunk, text, "explicit", 0.8)],
            )
            experiences.append(entry)

    def _build_evidence(self, chunk: Dict[str, Any], value: str, evidence_type: str, confidence: float) -> EvidenceDetail:
        return EvidenceDetail(
            value=value.strip(),
            evidence_text=self._text(chunk.get("content", "")),
            source_file=chunk.get("source_file", ""),
            page=int(chunk.get("page", 0) or 0),
            section=chunk.get("section", ""),
            evidence_type=evidence_type,
            confidence=confidence,
        )

    def _extract_title(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:2]:
            if re.search(r"\b(puesto|cargo|posición|role|title)\b", line, re.IGNORECASE):
                return line
        return lines[0] if lines else ""

    def _extract_company(self, text: str) -> str:
        match = re.search(r"\b(empresa|company|compañía)\s*[:\-]?\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(2).strip()
        return ""

    def _parse_dates(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        matches = list(DATE_PATTERN.finditer(text))
        if len(matches) == 1:
            return matches[0].group(0), None
        if len(matches) >= 2:
            return matches[0].group(0), matches[-1].group(0)
        return None, None

    def _estimate_duration(self, start: Optional[str], end: Optional[str]) -> Optional[float]:
        if not start:
            return None
        try:
            start_year = int(re.search(r"(\d{4})", start).group(1))
            end_year = int(re.search(r"(\d{4})", end).group(1)) if end else datetime.now().year
            if end_year < start_year:
                return None
            year_diff = float(end_year - start_year)
            if year_diff == 0.0:
                return 1.0
            if year_diff == 1.0:
                return 2.0
            return round(year_diff, 1)
        except Exception:
            return None

    def _consolidate_experiences(self, experiences: List[ExperienceEntry]) -> List[ExperienceEntry]:
        unique: Dict[str, ExperienceEntry] = {}
        for experience in experiences:
            key = f"{experience.title}:{experience.company}:{experience.start_date}:{experience.end_date}"
            existing = unique.get(key)
            if existing:
                existing.responsibilities.extend(experience.responsibilities)
                existing.achievements.extend(experience.achievements)
                existing.technologies.extend(experience.technologies)
                existing.evidence.extend(experience.evidence)
            else:
                unique[key] = experience
        return list(unique.values())

    def _calculate_total_experience(self, experiences: List[ExperienceEntry]) -> float:
        years = 0.0
        for exp in experiences:
            if exp.duration_years is not None:
                years += exp.duration_years
        return round(years, 1)

    def _estimate_years_by_technology(self, technologies: List[EvidenceDetail]) -> float:
        counts = len({tech.value.lower() for tech in technologies})
        return float(counts)

    def _estimate_confidence(self, experiences: List[ExperienceEntry], evidence: List[EvidenceDetail]) -> float:
        if not evidence and not experiences:
            return 0.0
        explicit = sum(1 for item in evidence if item.evidence_type == "explicit")
        confidence = round(min(1.0, explicit / max(1, len(evidence)) + 0.2), 2) if evidence else 0.0
        if experiences and confidence < 0.8:
            confidence = 0.8
        return confidence
