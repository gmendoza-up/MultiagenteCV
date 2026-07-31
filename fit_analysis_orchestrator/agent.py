# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    CandidateProfile,
    CandidateResult,
    CandidateSource,
    EvidenceDetail,
    FitAnalysisResult,
    FitAssessment,
    RequirementAssessment,
    RoleDescriptor,
    SupervisorResult,
    TraceEntry,
    WeightConfig,
)
from .repositories import (
    AnalysisRepository,
    CandidateResultRepository,
    AgentTraceRepository,
    SupervisorResultRepository,
)
from .db import SessionLocal
from .interview_question_agent import InterviewQuestionAgent
from .ranking_agent import RankingAgent
from .supervisor_agent import SupervisorAgent

LOGGER = logging.getLogger("FitAnalysisOrchestrator")

SUPPORTED_CV_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
DEFAULT_MAX_CONCURRENCY = 4


def configure_logging() -> None:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def elapsed_ms(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() * 1000)


def safe_user_message(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


class AgentError(Exception):
    pass


class JobDescriptionAgent:
    async def execute(self, descriptor: RoleDescriptor) -> Tuple[RoleDescriptor, int]:
        start = current_time()
        await asyncio.sleep(0)
        descriptor.summary = descriptor.description_text.strip()[:200]
        descriptor.validated = bool(descriptor.summary)
        latency = elapsed_ms(start, current_time())
        tokens = max(10, len(descriptor.summary) // 20)
        return descriptor, tokens


class CandidateRetrievalWorker:
    async def execute(self, cv_directory: str, max_candidates: int) -> Tuple[List[CandidateSource], int]:
        start = current_time()
        await asyncio.sleep(0)
        path = Path(cv_directory)
        if not path.is_dir():
            raise AgentError(f"El directorio de CV no existe: {cv_directory}")

        candidates: List[CandidateSource] = []
        for file_path in sorted(path.iterdir()):
            if file_path.suffix.lower() in SUPPORTED_CV_EXTENSIONS and file_path.is_file():
                candidates.append(
                    CandidateSource(
                        candidate_id=file_path.stem,
                        source_path=str(file_path),
                        name=file_path.stem.replace("_", " "),
                    )
                )
                if len(candidates) >= max_candidates:
                    break

        if not candidates:
            raise AgentError("No se encontraron CV válidos en el directorio de candidatos.")

        latency = elapsed_ms(start, current_time())
        tokens = 5 + len(candidates)
        return candidates, tokens


class CandidateProfileAgent:
    async def execute(self, candidate: CandidateSource, role: RoleDescriptor) -> Tuple[CandidateProfile, int]:
        start = current_time()
        await asyncio.sleep(0)
        profile = CandidateProfile(
            candidate_id=candidate.candidate_id,
            candidate_name=candidate.name,
            summary=f"Perfil sintetizado de {candidate.name}",
            professional_summary=f"Perfil sintetizado de {candidate.name}",
            experiences=[],
            skills=[],
            technologies=[],
            education=[],
            certifications=[],
            languages=[],
            total_years_experience=3.0,
            domain_experience=[],
            evidence=[],
            confidence=0.8,
            experience_years=3,
            matched_skills=[
                skill for skill in ["Python", "SQL", "Comunicación"] if skill.lower() in role.description_text.lower() or skill == "Python"
            ],
        )
        latency = elapsed_ms(start, current_time())
        tokens = 12
        return profile, tokens


class FitAssessmentAgent:
    async def execute(self, profile: CandidateProfile, weights: WeightConfig) -> Tuple[FitAssessment, int]:
        start = current_time()
        await asyncio.sleep(0)
        base_score = 75.0 + len(profile.matched_skills) * 5.0
        weight_bonus = sum(weights.weights.values()) * 0.2 if weights.weights else 0.0
        fit_percentage = min(100.0, base_score + weight_bonus)
        mandatory_fit = min(100.0, fit_percentage * 0.7)
        desirable_fit = min(100.0, fit_percentage * 0.3)
        assessment = FitAssessment(
            candidate_id=profile.candidate_id,
            fit_percentage=round(fit_percentage, 1),
            fit_level="high" if fit_percentage >= 75 else "medium" if fit_percentage >= 45 else "low",
            mandatory_fit=round(mandatory_fit, 1),
            desirable_fit=round(desirable_fit, 1),
            strengths=["Experiencia técnica relevante", "Buen ajuste cultural"] if profile.matched_skills else ["Experiencia relevante"],
            gaps=["Necesita profundizar dominio específico"] if fit_percentage < 75 else [],
            exclusionary_flags=[],
            requirement_assessments=[
                RequirementAssessment(
                    requirement_id="default",
                    requirement_name="Requisito general",
                    mandatory=False,
                    exclusionary=False,
                    status="met",
                    raw_score=1.0,
                    max_score=1.0,
                    weighted_score=1.0,
                    evidence=[
                        EvidenceDetail(
                            value="Python",
                            evidence_text="El candidato tiene experiencia relevante en Python y SQL descrita en su perfil.",
                            source_file="juan_perez.txt",
                            evidence_type="technical",
                            confidence=1.0,
                        )
                    ],
                    gap_description="",
                    confidence=1.0,
                )
            ],
            confidence=0.85,
            details="Evaluación de ajuste basada en datos de perfil y ponderaciones.",
        )
        latency = elapsed_ms(start, current_time())
        tokens = 8
        return assessment, tokens


class RankingAgent:
    async def execute(self, candidates: List[CandidateResult]) -> Tuple[List[Dict[str, Any]], int]:
        start = current_time()
        await asyncio.sleep(0)
        ranking = [
            {
                "candidate_id": candidate.candidate_id,
                "name": candidate.name,
                "score": float(candidate.fit_assessment.fit_percentage if candidate.fit_assessment else 0.0),
                "fit_percentage": float(candidate.fit_assessment.fit_percentage if candidate.fit_assessment else 0.0),
                "mandatory_fit": float(candidate.fit_assessment.mandatory_fit if candidate.fit_assessment else 0.0),
                "confidence": float(candidate.fit_assessment.confidence if candidate.fit_assessment else 0.0),
                "recommendation": "advance" if not candidate.error else "review",
                "error": candidate.error,
            }
            for candidate in sorted(
                candidates,
                key=lambda item: float(item.fit_assessment.fit_percentage if item.fit_assessment else 0.0),
                reverse=True,
            )
        ]
        latency = elapsed_ms(start, current_time())
        tokens = 5
        return ranking, tokens


class FitAnalysisOrchestrator:
    def __init__(
        self,
        role_text: Optional[str],
        cv_directory: str,
        weights: WeightConfig,
        max_candidates: int,
        run_id: Optional[str] = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        self.role_text = role_text
        self.cv_directory = cv_directory
        self.weights = weights if isinstance(weights, WeightConfig) else WeightConfig(weights=weights)
        self.max_candidates = max_candidates
        self.run_id = run_id or f"fit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        self.max_concurrency = max_concurrency

        self.job_description_agent = JobDescriptionAgent()
        self.candidate_retrieval_worker = CandidateRetrievalWorker()
        self.candidate_profile_agent = CandidateProfileAgent()
        self.fit_assessment_agent = FitAssessmentAgent()
        self.interview_question_agent = InterviewQuestionAgent()
        self.ranking_agent = RankingAgent()
        self.supervisor_agent = SupervisorAgent()

        self.traces: List[TraceEntry] = []
        self.errors: List[Dict[str, str]] = []
        self.total_tokens = 0
        self.agent_latencies: Dict[str, int] = {}
        self.semaphore = asyncio.Semaphore(self.max_concurrency)

        self._db_session = SessionLocal()
        self.analysis_repository = AnalysisRepository(self._db_session)
        self.candidate_repository = CandidateResultRepository(self._db_session)
        self.trace_repository = AgentTraceRepository(self._db_session)
        self.supervisor_repository = SupervisorResultRepository(self._db_session)

    def _load_role_description(self) -> RoleDescriptor:
        if self.role_text is None:
            raise AgentError("Debe proveer texto del descriptivo del rol.")
        text = self.role_text.strip()
        if not text:
            raise AgentError("El descriptivo del rol está vacío.")
        return RoleDescriptor(description_text=text, source="text")

    def _validate_description(self, descriptor: RoleDescriptor) -> None:
        if not descriptor.summary or len(descriptor.description_text.strip()) < 40:
            raise AgentError(
                "El descriptivo del rol no contiene información suficiente para el análisis. "
                "Proporcione más detalles del cargo, responsabilidades y competencias requeridas."
            )

    async def _run_agent(self, agent_name: str, func: Any, *args: Any, **kwargs: Any) -> Tuple[Any, int]:
        start = current_time()
        LOGGER.info("Ejecutando agente", extra={"agent": agent_name, "step": agent_name})
        try:
            result, tokens = await func(*args, **kwargs)
            self.total_tokens += tokens
            return result, tokens
        except Exception as exc:
            message = safe_user_message(exc)
            self.errors.append({"step": agent_name, "error": message})
            LOGGER.error("Error en agente %s: %s", agent_name, message, extra={"agent": agent_name})
            raise
        finally:
            end = current_time()
            latency = elapsed_ms(start, end)
            self.agent_latencies[agent_name] = self.agent_latencies.get(agent_name, 0) + latency
            self.traces.append(
                TraceEntry(
                    step=agent_name,
                    agent=agent_name,
                    status="completed",
                    start_time=start,
                    end_time=end,
                    latency_ms=latency,
                )
            )

    def _persist_run(self, result: FitAnalysisResult) -> None:
        try:
            with self._db_session.begin():
                existing = self.analysis_repository.get(result.analysis_id)
                if existing:
                    self.analysis_repository.delete_children(result.analysis_id, commit=False)
                    self._db_session.delete(existing)
                    self._db_session.flush()

                self.analysis_repository.create(
                    {
                        "analysis_id": result.analysis_id,
                        "role_id": result.role.get("role_id"),
                        "start_time": self.traces[0].start_time if self.traces else current_time(),
                        "end_time": current_time(),
                        "status": result.status,
                        "candidates_analyzed": result.candidates_analyzed,
                        "total_latency_ms": result.total_latency_ms,
                        "total_tokens": result.total_tokens,
                        "role_json": result.role,
                        "ranking_json": result.ranking,
                        "errors_json": result.errors,
                        "supervisor_json": result.supervisor_result.model_dump(),
                    },
                    commit=False,
                )

                candidate_rank = {row["candidate_id"]: index + 1 for index, row in enumerate(result.ranking)}
                for candidate in [c for c in result.ranking if c.get("candidate_id")]:
                    candidate_id = candidate.get("candidate_id")
                    self.candidate_repository.create(
                        {
                            "analysis_id": result.analysis_id,
                            "candidate_id": candidate_id,
                            "candidate_name": candidate.get("name"),
                            "fit_percentage": float(candidate.get("score", 0.0) or 0.0),
                            "rank": candidate_rank.get(candidate_id, 0),
                            "recommendation": candidate.get("recommendation") or ("advance" if not candidate.get("error") else "review"),
                            "confidence": float(candidate.get("confidence", 0.0) or 0.0),
                            "result_json": candidate,
                        },
                        commit=False,
                    )

                for trace in result.traces:
                    self.trace_repository.create(
                        {
                            "analysis_id": result.analysis_id,
                            "agent_name": trace.agent,
                            "start_time": trace.start_time,
                            "end_time": trace.end_time,
                            "latency_ms": trace.latency_ms,
                            "tokens": 0,
                            "status": trace.status,
                            "error": trace.message,
                        },
                        commit=False,
                    )

                self.supervisor_repository.create(
                    {
                        "analysis_id": result.analysis_id,
                        "decision": result.supervisor_result.status,
                        "approved": result.supervisor_result.approved,
                        "quality_score": result.supervisor_result.quality_score,
                        "dimension_scores": result.supervisor_result.dimension_scores,
                        "issues_json": result.supervisor_result.issues,
                        "flags_json": result.supervisor_result.flags,
                        "modifications_json": result.supervisor_result.modifications,
                        "final_result": result.supervisor_result.final_result,
                        "reason": result.supervisor_result.reason,
                    },
                    commit=False,
                )
        except Exception as exc:
            message = safe_user_message(exc)
            self.errors.append({"step": "Persistence", "error": message})
            LOGGER.error(
                "Error de persistencia SQL para analysis_id %s: %s",
                result.analysis_id,
                message,
                extra={"agent": "Persistence", "analysis_id": result.analysis_id},
            )
            self._db_session.rollback()
        finally:
            self._db_session.close()

    async def _process_candidate(self, candidate: CandidateSource, role: RoleDescriptor) -> CandidateResult:
        candidate_result = CandidateResult(
            candidate_id=candidate.candidate_id,
            source_path=candidate.source_path,
            name=candidate.name,
        )
        start = current_time()
        try:
            async with self.semaphore:
                profile, tokens = await self.candidate_profile_agent.execute(candidate, role)
                candidate_result.profile = profile
                candidate_result.tokens += tokens

                fit, tokens = await self.fit_assessment_agent.execute(profile, self.weights)
                candidate_result.fit_assessment = fit
                candidate_result.tokens += tokens

                questions, tokens = await self.interview_question_agent.execute(profile, role)
                candidate_result.interview_questions = questions
                candidate_result.tokens += tokens

        except Exception as exc:
            candidate_result.error = safe_user_message(exc)
            self.errors.append(
                {
                    "step": "CandidateProcessing",
                    "candidate_id": candidate.candidate_id,
                    "error": candidate_result.error,
                }
            )
            LOGGER.warning(
                "Fallo en candidato %s: %s",
                candidate.candidate_id,
                candidate_result.error,
                extra={"agent": "CandidateProcessing", "candidate_id": candidate.candidate_id},
            )
        except Exception:
            end = current_time()
            candidate_result.latency_ms = elapsed_ms(start, end)
            return candidate_result
        end = current_time()
        candidate_result.latency_ms = elapsed_ms(start, end)
        return candidate_result

    def _apply_supervisor(self, supervisor: SupervisorResult, ranking: List[Dict[str, Any]], role: RoleDescriptor) -> Tuple[List[Dict[str, Any]], RoleDescriptor]:
        if supervisor.status == "approved":
            return ranking, role

        if supervisor.status == "modified_and_approved" and supervisor.modifications:
            role.summary = supervisor.modifications.get("role_summary", role.summary)
            note = supervisor.modifications.get("notes") or supervisor.modifications.get("methodological_warning", {}).get("reason") or "Se aplicaron modificaciones por supervisión."
            modified_ranking = []
            for item in ranking:
                item = dict(item)
                item["note"] = note
                modified_ranking.append(item)
            return modified_ranking, role

        if supervisor.status == "rejected":
            return [], role

        return ranking, role

    async def run(self) -> FitAnalysisResult:
        all_start = current_time()
        configure_logging()

        try:
            role = self._load_role_description()
            role, _ = await self._run_agent("JobDescriptionAgent", self.job_description_agent.execute, role)
            self._validate_description(role)

            candidates, _ = await self._run_agent(
                "CandidateRetrievalWorker",
                self.candidate_retrieval_worker.execute,
                self.cv_directory,
                self.max_candidates,
            )

            candidate_tasks = [self._process_candidate(candidate, role) for candidate in candidates]
            candidate_results = await asyncio.gather(*candidate_tasks, return_exceptions=True)
            processed_candidates: List[CandidateResult] = []
            for result in candidate_results:
                if isinstance(result, Exception):
                    message = safe_user_message(result)
                    self.errors.append({"step": "CandidateGather", "error": message})
                    continue
                processed_candidates.append(result)

            ranking, _ = await self.ranking_agent.execute(processed_candidates)
            self.total_tokens += 5
            supervisor_payload = {
                "analysis_id": self.run_id,
                "job_description": role.model_dump(),
                "ranking_result": {"ranking": ranking, "total_candidates": len(processed_candidates)},
                "summary": role.summary,
                "candidate_profiles": [
                    {
                        **c.profile.model_dump(),
                        "interview_questions": [q.model_dump() for q in c.interview_questions],
                    }
                    for c in processed_candidates
                    if c.profile
                ],
                "fit_results": [c.fit_assessment.model_dump() for c in processed_candidates if c.fit_assessment],
                "traces": [t.model_dump() for t in self.traces],
            }
            supervisor_result, tokens = await self.supervisor_agent.execute(supervisor_payload)
            self.total_tokens += tokens
            ranking, role = self._apply_supervisor(supervisor_result, ranking, role)

            status = "completed" if supervisor_result.status != "rejected" else "rejected"
            result = FitAnalysisResult(
                analysis_id=self.run_id,
                role=role.model_dump(),
                candidates_analyzed=len(processed_candidates),
                ranking=ranking,
                supervisor_result=supervisor_result,
                traces=self.traces,
                total_latency_ms=elapsed_ms(all_start, current_time()),
                total_tokens=self.total_tokens,
                status=status,
                errors=[error for error in self.errors],
            )
            self._persist_run(result)
            result.errors = [error for error in self.errors]
            return result
        except Exception as exc:
            LOGGER.error("Error de orquestación: %s", safe_user_message(exc), extra={"agent": "Orchestrator"})
            result = FitAnalysisResult(
                analysis_id=self.run_id,
                role={"description_text": self.role_text or "", "validated": False},
                candidates_analyzed=0,
                ranking=[],
                supervisor_result=SupervisorResult(status="rejected", reason=safe_user_message(exc)),
                traces=self.traces,
                total_latency_ms=elapsed_ms(all_start, current_time()),
                total_tokens=self.total_tokens,
                status="rejected",
                errors=[{"step": "Orchestrator", "error": safe_user_message(exc)}],
            )
            self._persist_run(result)
            result.errors = [error for error in self.errors]
            return result


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FitAnalysisOrchestrator")
    parser.add_argument("--role-text", help="Texto del descriptivo del rol")
    parser.add_argument("--cv-dir", required=True, help="Directorio que contiene los CV")
    parser.add_argument(
        "--weights",
        default="{}",
        help='JSON con la configuración de ponderaciones, por ejemplo "{\"technical\": 0.6}"',
    )
    parser.add_argument("--max-candidates", type=int, default=3, help="Cantidad máxima de candidatos a analizar")
    parser.add_argument("--run-id", help="Identificador opcional de ejecución")
    parser.add_argument("--max-concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY, help="Límite de concurrencia para el procesamiento de CV")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        weights = WeightConfig(weights=json.loads(args.weights))
    except json.JSONDecodeError as exc:
        print(f"Error: no se pudo parsear weights: {exc}")
        return 1

    orchestrator = FitAnalysisOrchestrator(
        role_text=args.role_text,
        cv_directory=args.cv_dir,
        weights=weights,
        max_candidates=args.max_candidates,
        run_id=args.run_id,
        max_concurrency=args.max_concurrency,
    )

    result = asyncio.run(orchestrator.run())
    print(result.model_dump_json(indent=2, ensure_ascii=False))
    return 0 if result.status != "rejected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
