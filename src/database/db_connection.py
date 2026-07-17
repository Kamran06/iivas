"""Thin SQLAlchemy engine factory used by all DB-touching modules."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.config_loader import db_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(db_url(), pool_pre_ping=True, future=True)
