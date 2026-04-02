from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from runtime_app.lib.config import settings


_engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)


@contextmanager
def db_session() -> Session:
    session = Session(_engine)
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
