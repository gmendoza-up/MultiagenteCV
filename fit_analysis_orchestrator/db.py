# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SessionType
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fit_analysis.db")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Iterator[SessionType]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models_sql as models_module

    Base.metadata.create_all(bind=engine)
