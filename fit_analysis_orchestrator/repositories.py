# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import models_sql


class AnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: Dict[str, Any], commit: bool = True) -> models_sql.AnalysisRun:
        analysis = models_sql.AnalysisRun(**data)
        self.db.add(analysis)
        if commit:
            self.db.commit()
            self.db.refresh(analysis)
        else:
            self.db.flush()
            self.db.refresh(analysis)
        return analysis

    def get(self, analysis_id: str) -> Optional[models_sql.AnalysisRun]:
        return self.db.get(models_sql.AnalysisRun, analysis_id)

    def update(self, analysis_id: str, fields: Dict[str, Any], commit: bool = True) -> Optional[models_sql.AnalysisRun]:
        analysis = self.get(analysis_id)
        if not analysis:
            return None
        for key, value in fields.items():
            setattr(analysis, key, value)
        self.db.add(analysis)
        if commit:
            self.db.commit()
            self.db.refresh(analysis)
        else:
            self.db.flush()
            self.db.refresh(analysis)
        return analysis

    def delete_children(self, analysis_id: str, commit: bool = True) -> None:
        self.db.query(models_sql.CandidateResult).filter_by(analysis_id=analysis_id).delete(synchronize_session=False)
        self.db.query(models_sql.AgentTrace).filter_by(analysis_id=analysis_id).delete(synchronize_session=False)
        self.db.query(models_sql.SupervisorResult).filter_by(analysis_id=analysis_id).delete(synchronize_session=False)
        if commit:
            self.db.commit()
        else:
            self.db.flush()


class CandidateResultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: Dict[str, Any], commit: bool = True) -> models_sql.CandidateResult:
        candidate = models_sql.CandidateResult(**data)
        self.db.add(candidate)
        if commit:
            self.db.commit()
            self.db.refresh(candidate)
        else:
            self.db.flush()
            self.db.refresh(candidate)
        return candidate

    def list_by_analysis(self, analysis_id: str) -> List[models_sql.CandidateResult]:
        return self.db.query(models_sql.CandidateResult).filter_by(analysis_id=analysis_id).all()

    def delete_by_analysis(self, analysis_id: str, commit: bool = True) -> None:
        self.db.query(models_sql.CandidateResult).filter_by(analysis_id=analysis_id).delete(synchronize_session=False)
        if commit:
            self.db.commit()
        else:
            self.db.flush()


class AgentTraceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: Dict[str, Any], commit: bool = True) -> models_sql.AgentTrace:
        trace = models_sql.AgentTrace(**data)
        self.db.add(trace)
        if commit:
            self.db.commit()
            self.db.refresh(trace)
        else:
            self.db.flush()
            self.db.refresh(trace)
        return trace

    def list_by_analysis(self, analysis_id: str) -> List[models_sql.AgentTrace]:
        return self.db.query(models_sql.AgentTrace).filter_by(analysis_id=analysis_id).all()

    def delete_by_analysis(self, analysis_id: str, commit: bool = True) -> None:
        self.db.query(models_sql.AgentTrace).filter_by(analysis_id=analysis_id).delete(synchronize_session=False)
        if commit:
            self.db.commit()
        else:
            self.db.flush()


class SupervisorResultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, data: Dict[str, Any], commit: bool = True) -> models_sql.SupervisorResult:
        supervisor_result = models_sql.SupervisorResult(**data)
        self.db.add(supervisor_result)
        if commit:
            self.db.commit()
            self.db.refresh(supervisor_result)
        else:
            self.db.flush()
            self.db.refresh(supervisor_result)
        return supervisor_result

    def get_by_analysis(self, analysis_id: str) -> Optional[models_sql.SupervisorResult]:
        return self.db.query(models_sql.SupervisorResult).filter_by(analysis_id=analysis_id).one_or_none()

    def delete_by_analysis(self, analysis_id: str, commit: bool = True) -> None:
        self.db.query(models_sql.SupervisorResult).filter_by(analysis_id=analysis_id).delete(synchronize_session=False)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
