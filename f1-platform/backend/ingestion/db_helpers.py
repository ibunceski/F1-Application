from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

_engine: Engine | None = None
_session_local: sessionmaker[Session] | None = None


def _to_sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


def get_sync_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")
    _engine = create_engine(_to_sync_database_url(database_url), future=True)
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(
            bind=get_sync_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _session_local


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert(
    session: Session,
    model_class: type[Any],
    conflict_column: str | list[str] | tuple[str, ...],
    data_dict: dict[str, Any],
) -> Any:
    conflict_columns = (
        [conflict_column] if isinstance(conflict_column, str) else list(conflict_column)
    )
    table = model_class.__table__
    statement = insert(table).values(**data_dict)

    update_values = {
        column_name: statement.excluded[column_name]
        for column_name in data_dict
        if column_name not in {"id", *conflict_columns}
    }

    if update_values:
        statement = statement.on_conflict_do_update(
            index_elements=[table.c[column_name] for column_name in conflict_columns],
            set_=update_values,
        )
    else:
        statement = statement.on_conflict_do_nothing(
            index_elements=[table.c[column_name] for column_name in conflict_columns],
        )

    primary_key_column = next(iter(table.primary_key.columns))
    result = session.execute(statement.returning(primary_key_column))
    primary_key = result.scalar_one()
    return session.get(model_class, primary_key)
